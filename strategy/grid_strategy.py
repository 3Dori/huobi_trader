import warnings
from datetime import datetime
import threading
import time

import numpy as np

from huobi.constant import *

from trader import BaseTrader
from .runnable_strategy import RunnableStrategy
from .single_pair_strategy import SinglePairStrategy


class GridStrategy(SinglePairStrategy, RunnableStrategy):
    def __init__(self, trader: BaseTrader, symbol, target_asset, base_asset, lower_price, upper_price, num_grids,
                 grid_type='arithmetic', transaction_strategy='even', geom_ratio=2, start_with_market_order=True,
                 take_profit=None, stop_loss=None, min_price_to_start=None, max_price_to_start=None,
                 enable_logger=True, root_dir=None, interval=10):
        SinglePairStrategy.__init__(self, trader, symbol, target_asset, base_asset,
                                    enable_logger=enable_logger, root_dir=root_dir)
        RunnableStrategy.__init__(self, interval)
        self.lower_price = lower_price
        self.upper_price = upper_price
        self.num_finished_orders = 0

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
        if minimum_profit <= trader.FEE * 2:
            raise ValueError(f'Profit is too small: {minimum_profit}')
        self.orders = [None] * len(self.grids)
        self.curr_buy_order_id = None
        self.curr_sell_order_id = None

        if transaction_strategy not in ('even', 'geom'):    # Warning: geom is a bad strategy
            raise ValueError(f'Unknown transaction_strategy: {transaction_strategy}')
        self.transaction_strategy = transaction_strategy
        self.geom_ratio = geom_ratio
        self.start_with_market_order = start_with_market_order

        if take_profit is not None and take_profit <= upper_price:
            raise ValueError('take_profit must be greater than upper_price')
        if stop_loss is not None and stop_loss >= lower_price:
            raise ValueError('stop_loss must be less than lower_price')
        if min_price_to_start is not None and min_price_to_start <= lower_price:
            raise ValueError('min_price_to_start must be greater than lower_price')
        if max_price_to_start is not None and max_price_to_start >= upper_price:
            raise ValueError('max_price_to_start must be less than upper_price')
        if min_price_to_start is not None and max_price_to_start is not None:
            if min_price_to_start >= max_price_to_start:
                raise ValueError('min_price_to_start must be less than max_price_to_start')
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.min_price_to_start = min_price_to_start
        self.max_price_to_start = max_price_to_start

        self.prev_grid = -1
        self.subscription = None

    def print_strategy_info(self):
        current_asset = self.get_total_asset(in_base=True) if self._started else 1.0
        initial_total_asset_in_base = self.initial_total_asset_in_base if self._started else 1.0
        if self.grid_type == 'arithmetic':
            profit_per_grid = f'{(self.grids[-1]/self.grids[-2] - 1 - self.trader.FEE*2)*100:.2f}% - ' \
                              f'{(self.grids[1]/self.grids[0] - 1 - self.trader.FEE*2)*100:.2f}%'
        else:
            profit_per_grid = f'{(self.grids[1]/self.grids[0] - 1 - self.trader.FEE*2)*100:.2f}%'
        grids = []
        for i, grid in enumerate(self.grids):
            if i == self.prev_grid - 1:
                grids.append(f'[{grid:.{self.pair.price_scale}f}]')
            else:
                grids.append(f'{grid:.{self.pair.price_scale}f}')
        grids = ', '.join(grids)
        print(f'============ Grid strategy =============\n'
              f'Started at {self.start_time.strftime("%Y/%m/%d %H%:%M:%S")}\n'
              f'Start assets:\n'
              f'  Price: {self.initial_price:.{self.pair.price_scale}f}\n'
              f'  {self.base_symbol}: {self.initial_base_asset:.{self.pair.price_scale}f}\n'
              f'  {self.target_symbol}: {self.initial_target_asset:.{self.pair.amount_scale}f}\n'
              f'  In base currency: {initial_total_asset_in_base:.{self.pair.price_scale}f}\n'
              f'Current assets:\n'
              f'  Price: {self.newest_price:.{self.pair.price_scale}f}\n'
              f'  {self.base_symbol}: {self.base_asset:.{self.pair.price_scale}f}\n'
              f'  {self.target_symbol}: {self.target_asset:.{self.pair.amount_scale}f}\n'
              f'  In base currency: {current_asset:.{self.pair.price_scale}f}\n'
              f'Grids:\n'
              f'  {grids}\n'
              f'Profit per grid: {profit_per_grid}\n'
              f'Finished orders: {self.num_finished_orders}\n'
              f'Profit:\n'
              f'  {current_asset - initial_total_asset_in_base:.{self.pair.price_scale}} {self.base_symbol}\n'
              f'  {(current_asset/initial_total_asset_in_base - 1)*100:.2f}%\n'
              f'=========================================')

    def get_profit_in_percentage(self):
        current_asset = self.get_total_asset(in_base=True)
        return (current_asset/self.initial_total_asset_in_base - 1) * 100

    def create_initial_market_order(self, curr_grid):
        initial_total_asset_in_base = self.get_total_asset()[0]
        assumed_asset = initial_total_asset_in_base * curr_grid / (self.num_grids + 1)
        if assumed_asset > self.base_asset:
            diff = assumed_asset - self.base_asset
            amount = diff / self.newest_price
            if amount > 10 ** (-self.pair.amount_scale):
                self.create_order(None, OrderType.SELL_MARKET, amount)
        elif assumed_asset < self.base_asset:
            amount = self.base_asset - assumed_asset
            if amount > 10 ** (-self.pair.price_scale):
                self.create_order(None, OrderType.BUY_MARKET, amount)

    def get_newest_grid(self):
        return np.searchsorted(self.grids, self.newest_price)

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
                self.logger.error('Unfilled order detected')
            else:
                raise RuntimeError('Unfilled order detected')
        if self.enable_logger:
            self.logger.info(f'Filled order confirmed. Type: {order.type}; '
                             f'price: {float(order.price):.{self.pair.price_scale}f}; '
                             f'amount: {float(order.filled_amount):.{self.pair.amount_scale}f}')
        self.num_finished_orders += 1
        # if order.type == OrderType.BUY_LIMIT:
        #     self.target_asset += float(order.filled_amount) - float(order.filled_fees)
        #     self.base_asset -= float(order.filled_cash_amount)
        # elif order.type == OrderType.SELL_LIMIT:
        #     self.target_asset -= float(order.filled_amount)
        #     self.base_asset += float(order.filled_cash_amount) - float(order.filled_fees)
        self.cancel_orders([order for order in self.orders if order is not None and order != order_id])
        self.orders = [None] * len(self.grids)
        self.curr_sell_order_id = None
        self.curr_buy_order_id = None

    def handle_trade_clear(self, trade_clearing_event):
        trade_clearing = trade_clearing_event.data
        if trade_clearing.orderType in (OrderType.BUY_LIMIT, OrderType.BUY_MARKET):
            self.target_asset += float(trade_clearing.tradeVolume) - float(trade_clearing.transactFee)
            self.base_asset -= float(trade_clearing.tradeVolume) * float(trade_clearing.tradePrice)
        elif trade_clearing.orderType in (OrderType.SELL_LIMIT, OrderType.SELL_MARKET):
            self.target_asset -= float(trade_clearing.tradeVolume)
            self.base_asset += float(trade_clearing.tradeVolume) * float(trade_clearing.tradePrice) - float(trade_clearing.transactFee)
        assert abs(self.base_asset - self.trader.get_balance(self.base_symbol)) <= 1e-4, f'{self.base_asset}, {self.trader.get_balance(self.base_symbol)}'

    def feed(self, price):
        if self.take_profit is not None and price > self.take_profit:
            self.stop()
            return
        if self.stop_loss is not None and price < self.stop_loss:
            self.stop(sell_at_market_price=True)
            return
        self.newest_price = price
        curr_sell_order = self.curr_sell_order_id and self.trader.get_order(self.curr_sell_order_id)
        curr_buy_order = self.curr_buy_order_id and self.trader.get_order(self.curr_buy_order_id)
        curr_grid = self.get_newest_grid()
        if curr_sell_order is not None and curr_sell_order.state == OrderState.FILLED:
            self.confirm_order_finished(self.curr_sell_order_id, curr_sell_order)
            if curr_grid == self.prev_grid:
                curr_grid += 1    # handling latency between transaction and price-reading
            if curr_grid <= self.num_grids:
                self.create_sell_order(curr_grid)
            if curr_grid - 2 >= 0 and self.orders[curr_grid - 2] is None:
                self.create_buy_order(curr_grid - 2)
        elif curr_buy_order is not None and curr_buy_order.state == OrderState.FILLED:
            self.confirm_order_finished(self.curr_buy_order_id, curr_buy_order)
            if curr_grid == self.prev_grid:
                curr_grid -= 1    # handling latency between transaction and price-reading
            if curr_grid - 1 >= 0:
                self.create_buy_order(curr_grid - 1)
            if curr_grid + 1 <= self.num_grids and self.orders[curr_grid + 1] is None:
                self.create_sell_order(curr_grid + 1)
        if curr_grid >= self.num_grids > self.prev_grid:
            if self.enable_logger:
                self.logger.warning('The newest price has exceeded upper bound of the grid.')
        elif curr_grid <= 0 < self.prev_grid:
            if self.enable_logger:
                self.logger.warning('The newest price has exceeded lower bound of the grid.')
        self.prev_grid = curr_grid

    def start_impl(self, price=None):
        self.trader.add_trader_clearing_subscription(self.symbol, self.handle_trade_clear, None)
        if price is None:
            price = self.trader.get_newest_price(self.symbol)
        self.newest_price = price
        self.initial_total_asset_in_base = self.get_total_asset(in_base=True)
        self.initial_price = price
        self.start_time = datetime.now()
        if self.upper_price <= self.newest_price or self.lower_price >= self.newest_price:
            raise RuntimeError('Unable to start a transaction because the current price is beyond the range')

        if self.enable_logger:
            self.logger.info('Grid strategy started')
        curr_grid = self.get_newest_grid()
        if self.start_with_market_order:
            self.create_initial_market_order(curr_grid)
        if curr_grid - 1 >= 0:
            self.create_buy_order(curr_grid - 1)    # create initial buy limit order
        if curr_grid <= self.num_grids:
            self.create_sell_order(curr_grid)    # create initial sell limit order
        self.prev_grid = curr_grid

    def check_start_condition(self):
        if self.min_price_to_start is None and self.max_price_to_start is None:
            return
        while True:
            if self._stopped:
                if self.enable_logger:
                    self.logger.info('Strategy successfully stopped')
                return
            newest_price = self.trader.get_newest_price(self.symbol)
            min_price_satisfied = self.min_price_to_start is None or newest_price >= self.min_price_to_start
            max_price_satisfied = self.max_price_to_start is None or newest_price <= self.max_price_to_start
            if min_price_satisfied and max_price_satisfied:
                break
            time.sleep(self.interval)

    def stop(self, sell_at_market_price=False):
        self.trader.remove_trader_clearing_subscription()
        if sell_at_market_price:
            self.create_order(None, OrderType.SELL_MARKET, self.target_asset)
        self.logger.info('Stopping grid strategy')
        order_list = [order_id for order_id in (self.curr_sell_order_id, self.curr_buy_order_id) if order_id]
        if order_list:
            self.cancel_orders(order_list)
        super().stop()
