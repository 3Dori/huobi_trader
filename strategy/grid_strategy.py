import warnings
from datetime import datetime
import threading
import time

import numpy as np

from huobi.constant import *

from constants import *
from trader import BaseTrader
from .base_strategy import BaseStrategy


class GridStrategy(BaseStrategy):
    def __init__(self, trader: BaseTrader, symbol, target_asset, base_asset, lower_price, upper_price, num_grids,
                 grid_type='arithmetic', transaction_strategy='even', geom_ratio=2,
                 stop_loss=None,
                 enable_logger=True, root_dir=None, interval=10):
        super().__init__(enable_logger=enable_logger, root_dir=root_dir)
        self.trader = trader
        self.symbol = symbol
        self.start_time = datetime.now()
        target_balance, base_balance = self.trader.get_balance_pair(symbol)
        if target_balance < target_asset:
            raise RuntimeError(f'Insufficient balance for {self.target_symbol}')
        if base_balance < base_asset:
            raise RuntimeError(f'Insufficient balance for {self.base_symbol}')
        self.target_asset = target_asset
        self.base_asset = base_asset
        self.initial_target_asset = target_asset
        self.initial_base_asset = base_asset
        self.initial_total_asset_in_base = 0
        self.newest_price = 0
        self.lower_price = lower_price
        self.upper_price = upper_price

        if lower_price >= upper_price:
            raise ValueError('lower_price must be higher than upper_price')
        if num_grids < 2 or num_grids > 99:
            raise ValueError('grid_num must be between 2 and 99')
        self.num_grids = num_grids
        self.grid_type = grid_type
        if grid_type == 'arithmetic':
            self.grids = np.linspace(lower_price, upper_price, num_grids + 1)
        elif grid_type == 'geometric':
            self.grids = np.geomspace(lower_price, upper_price, num_grids + 1)
        else:
            raise ValueError(f'Unknown grid_type: {grid_type}')
        minimum_profit = self.grids[-1] / self.grids[-2] - 1
        if minimum_profit <= BaseTrader.FEE * 2:
            raise ValueError(f'Profit is too small: {minimum_profit}')
        self.orders = [None] * len(self.grids)
        self.curr_buy_order_id = None
        self.curr_sell_order_id = None

        if transaction_strategy not in ('even', 'geom'):    # Warning: geom is a bad strategy
            raise ValueError(f'Unknown transaction_strategy: {transaction_strategy}')
        self.transaction_strategy = transaction_strategy
        self.geom_ratio = geom_ratio

        if stop_loss is not None and stop_loss >= lower_price:
            raise ValueError('stop_loss must be less than lower_price')
        self.stop_loss = stop_loss

        if interval is not None and interval < 0:
            raise ValueError('interval must be greater than 0')
        self.interval = interval
        self.prev_grid = -1
        self.thread = None

    @property
    def base_symbol(self):
        return transaction_pairs[self.symbol].base

    @property
    def target_symbol(self):
        return transaction_pairs[self.symbol].target

    def print_strategy_info(self):
        current_asset = self.get_total_asset(in_base=True)
        pair = transaction_pairs[self.symbol]
        if self.grid_type == 'arithmetic':
            profit_per_grid = f'{self.grids[-1]/self.grids[-2]*100:.2f}% - {self.grids[1]/self.grids[0]*100:.2f}%'
        else:
            profit_per_grid = f'{self.grids[1]/self.grids[0]*100:.2f}%'
        print(f'============ Grid strategy =============\n'
              f'Started at {self.start_time.strftime("%Y/%m/%d")}\n'
              f'Start assets:\n'
              f'  {self.base_symbol}: {self.initial_base_asset:.{pair.price_scale}f}\n'
              f'  {self.target_symbol}: {self.initial_target_asset:.{pair.amount_scale}f}\n'
              f'  In base currency: {self.initial_total_asset_in_base:.{pair.price_scale}f}\n'
              f'Current assets:\n'
              f'  {self.base_symbol}: {self.base_asset:.{pair.price_scale}f}\n'
              f'  {self.target_symbol}: {self.target_asset:.{pair.amount_scale}f}\n'
              f'  In base currency: {current_asset:.{pair.price_scale}f}\n'
              f'Profit per grid:\n'
              f'  {profit_per_grid}\n'
              f'Profit:\n'
              f'  {(current_asset/self.initial_total_asset_in_base - 1) * 100:.2f}%\n'
              f'=========================================')

    def get_profit_in_percentage(self):
        current_asset = self.get_total_asset(in_base=True)
        return (current_asset/self.initial_total_asset_in_base - 1) * 100

    def get_total_asset(self, in_base=False):
        total_asset_in_base = self.base_asset + self.target_asset * self.newest_price
        total_asset_in_target = total_asset_in_base / self.newest_price
        if in_base:
            return total_asset_in_base
        else:
            return total_asset_in_base, total_asset_in_target

    def create_initial_order(self, curr_grid):
        initial_total_asset_in_base = self.get_total_asset()[0]
        assumed_asset = initial_total_asset_in_base * curr_grid / (self.num_grids + 1)
        if assumed_asset > self.base_asset:
            diff = assumed_asset - self.base_asset
            amount = diff / self.newest_price
            try:
                self.create_order(None, OrderType.SELL_MARKET, amount)
            except RuntimeError as e:
                if self.enable_logger:
                    self.logger.warning(f'Unable to create initial order: {e.args}')
                else:
                    warnings.warn(f'Unable to create initial order: {e.args}')
        elif assumed_asset < self.base_asset:
            amount = self.base_asset - assumed_asset
            try:
                self.create_order(None, OrderType.BUY_MARKET, amount)
            except RuntimeError as e:
                if self.enable_logger:
                    self.logger.warning('Unable to create initial order')
                else:
                    warnings.warn(f'Unable to create initial order: {e.args}')
        if curr_grid - 1 >= 0:
            self.create_buy_order(curr_grid - 1)    # create initial buy limit order
        if curr_grid <= self.num_grids:
            self.create_sell_order(curr_grid)    # create initial sell limit order

    def get_newest_grid(self):
        return np.searchsorted(self.grids, self.newest_price)

    def create_order(self, price, order_type, amount=None):
        try:
            order_id = self.trader.create_order(self.symbol, price, order_type, amount)
            if order_type == OrderType.BUY_MARKET:
                order = self.trader.get_order(order_id)
                self.base_asset -= float(order.filled_cash_amount)
                self.target_asset += float(order.filled_amount) - float(order.filled_fees)
            elif order_type == OrderType.SELL_MARKET:
                order = self.trader.get_order(order_id)
                self.base_asset += float(order.filled_cash_amount) - float(order.filled_fees)
                self.target_asset -= float(order.filled_amount)
            if order_type in (OrderType.BUY_MARKET, OrderType.SELL_MARKET):
                price = self.newest_price
            if self.enable_logger:
                self.logger.info(f'Created order. Order type: {order_type}; price: {price}; amount: {amount}')
            return order_id
        except Exception as e:
            if self.enable_logger:
                self.logger.error(f'Unable to create order. Order type: {order_type}; price: {price}; '
                                  f'amount: {amount}; error: {e.args}')
            else:
                raise e

    def create_buy_order(self, grid):
        assert self.orders[grid] is None
        price = self.grids[grid]
        if self.transaction_strategy == 'even':
            amount = self.base_asset / (grid+1) / price
        elif self.transaction_strategy == 'geom':
            amount = self.base_asset / self.geom_ratio / price
        else:
            raise NotImplementedError()
        order_id = self.create_order(self.grids[grid], OrderType.BUY_LIMIT, amount)
        self.orders[grid] = order_id
        self.curr_buy_order_id = order_id

    def create_sell_order(self, grid):
        assert self.orders[grid] is None
        price = self.grids[grid]
        if self.transaction_strategy == 'even':
            amount = self.target_asset / (self.num_grids-grid+1)
        elif self.transaction_strategy == 'geom':
            amount = self.target_asset / self.geom_ratio
        else:
            raise NotImplementedError()
        order_id = self.create_order(price, OrderType.SELL_LIMIT, amount)
        self.orders[grid] = order_id
        self.curr_sell_order_id = order_id

    def confirm_order_finished(self, order_id, order):
        if order.state != OrderState.FILLED:
            if self.enable_logger:
                self.logger.error('Unfinished order detected')
            else:
                raise RuntimeError('Unfinished order detected')
        if self.enable_logger:
            self.logger.info(f'Finished order confirmed. Order type: {order.type}; '
                             f'price: {order.price}; amount: {order.filled_amount}')
        if order.type == OrderType.BUY_LIMIT:
            self.target_asset += float(order.filled_amount) - float(order.filled_fees)
            self.base_asset -= float(order.filled_cash_amount)
        elif order.type == OrderType.SELL_LIMIT:
            self.target_asset -= float(order.filled_amount)
            self.base_asset += float(order.filled_cash_amount) - float(order.filled_fees)
        self.trader.cancel_orders(self.symbol,
                                  [order for order in self.orders if order is not None and order != order_id])
        self.orders = [None] * len(self.grids)
        self.curr_sell_order_id = None
        self.curr_buy_order_id = None

    def feed(self, price):
        if self.stop_loss is not None and price < self.stop_loss:
            self.stop(sell_at_market_price=True)
            return
        self.newest_price = price
        curr_grid = self.get_newest_grid()
        curr_sell_order = self.curr_sell_order_id and self.trader.get_order(self.curr_sell_order_id)
        curr_buy_order = self.curr_buy_order_id and self.trader.get_order(self.curr_buy_order_id)
        if curr_sell_order is not None and curr_sell_order.state == OrderState.FILLED:
            self.confirm_order_finished(self.curr_sell_order_id, curr_sell_order)
            if curr_grid <= self.num_grids:
                self.create_sell_order(curr_grid)
            if curr_grid - 2 >= 0 and self.orders[curr_grid - 2] is None:
                self.create_buy_order(curr_grid - 2)
        elif curr_buy_order is not None and curr_buy_order.state == OrderState.FILLED:
            self.confirm_order_finished(self.curr_buy_order_id, curr_buy_order)
            if curr_grid - 1 >= 0:
                self.create_buy_order(curr_grid - 1)
            if curr_grid + 1 <= self.num_grids and self.orders[curr_grid + 1] is None:
                self.create_sell_order(curr_grid + 1)
        self.prev_grid = curr_grid

    def start(self, price=None):
        if price is None:
            price = self.trader.get_newest_price(self.symbol)
        self.newest_price = price
        self.initial_total_asset_in_base = self.get_total_asset(in_base=True)
        self.start_time = datetime.now()
        if self.upper_price <= self.newest_price or self.lower_price >= self.newest_price:
            raise RuntimeError('Unable to start a transaction because the current price is beyond the range')

        curr_grid = self.get_newest_grid()
        self.create_initial_order(curr_grid)
        self.prev_grid = curr_grid

        if self.enable_logger:
            self.logger.info('Grid strategy started')
        if self.interval is not None:
            self.thread = threading.Thread(target=self.run, args=())
            self.thread.start()

    def run(self):
        assert self.interval is not None
        while True:
            if self._stopped:
                if self.enable_logger:
                    self.logger.info('Strategy successfully stopped')
                return
            try:
                newest_price = self.trader.get_newest_price(self.symbol)
                self.feed(newest_price)
            except RuntimeError:
                if self.enable_logger:
                    self.logger.error('Unable to read the newest price from the trader')
            time.sleep(self.interval)

    def stop(self, sell_at_market_price=False):
        if sell_at_market_price:
            self.create_order(None, OrderType.SELL_MARKET, self.target_asset)
        self.logger.info('Stopping grid strategy')
        super().stop()
