import warnings
from datetime import datetime

import numpy as np

from huobi.constant import *

from constants import *
from trader import BaseTrader
from logger import Logger


class GridStrategy(object):
    STAY = 0
    UP = 1
    DOWN = -1

    def __init__(self, trader: BaseTrader, symbol, target_asset, base_asset, lower_price, upper_price,
                 num_grids, grid_type='arithmetic', transaction_strategy='even', geom_ratio=2,
                 enable_logger=True, root_dir=None):
        self.logger = Logger(root_dir, 'Grid strategy') if enable_logger else None
        self.enable_logger = enable_logger
        self.trader = trader
        self.symbol = symbol
        self.start_time = datetime.now()
        target_balance, base_balance = self.trader.get_balance_pair(symbol)
        if target_balance < target_asset:
            raise RuntimeError(f'Insufficient balance for {self.target_symbol}')
        if base_balance < target_asset:
            raise RuntimeError(f'Insufficient balance for {self.base_symbol}')
        self.target_asset = target_asset
        self.base_asset = base_asset
        self.initial_target_asset = target_asset
        self.initial_base_asset = base_asset
        self.initial_total_asset_in_base = self.get_total_asset(in_base=True)
        self.newest_price = 0
        self.lower_price = lower_price
        self.upper_price = upper_price

        if lower_price >= upper_price:
            raise ValueError('lower_price must be higher than upper_price')
        if num_grids < 2 or num_grids > 99:
            raise ValueError('grid_num must be between 2 and 99')
        self.num_grids = num_grids
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

        if transaction_strategy not in ('even', 'geom'):    # Warning: geom is a bad strategy
            raise ValueError(f'Unknown transaction_strategy: {transaction_strategy}')
        self.transaction_strategy = transaction_strategy
        self.geom_ratio = geom_ratio

        self.prev_grid = -1
        self.prev_move = GridStrategy.STAY

    @property
    def base_symbol(self):
        return transaction_pairs[self.symbol].base

    @property
    def target_symbol(self):
        return transaction_pairs[self.symbol].target

    def print_strategy_info(self):
        current_asset = self.get_total_asset(in_base=True)
        print(f'============ Grid strategy =============\n'
              f'Started at {self.start_time.strftime("%Y/%m/%d")}\n'
              f'Start assets:\n'
              f'  {self.base_symbol}: {self.initial_base_asset}'
              f'  {self.target_symbol}: {self.initial_target_asset}'
              f'Current assets:\n'
              f'  {self.base_symbol}: {self.base_asset}\n'
              f'  {self.target_symbol}: {self.target_asset}\n'
              f'  In base currency: {current_asset}'
              f'Profit:\n'
              f'  {(1 - current_asset / self.initial_total_asset_in_base) / 100}%'
              f'=========================================')

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
                    self.logger.warning(f'Unable to create initial order: {e.args[0]}')
                else:
                    warnings.warn(f'Unable to create initial order: {e.args[0]}')
        elif assumed_asset < self.base_asset:
            diff = self.base_asset - assumed_asset
            amount = diff / self.newest_price
            try:
                self.create_order(None, OrderType.BUY_MARKET, amount)
            except RuntimeError as e:
                if self.enable_logger:
                    self.logger.warning('Unable to create initial order')
                else:
                    warnings.warn(f'Unable to create initial order: {e.args[0]}')
        if curr_grid - 1 >= 0:
            self.create_buy_order(curr_grid - 1)    # create initial buy limit order
        if curr_grid <= self.num_grids:
            self.create_sell_order(curr_grid)    # create initial sell limit order

    def get_newest_grid(self):
        return np.searchsorted(self.grids, self.newest_price)

    def create_order(self, price, order_type, amount=None, amount_fraction=None):
        try:
            order_id = self.trader.create_order(self.symbol, price, order_type, amount, amount_fraction)
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
                self.logger.error(f'Unable to create order. Order type: {order_type}; price: {self.newest_price}; '
                                  f'amount: {amount}; error: {e.args[0]}')
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
        self.orders[grid] = self.create_order(self.grids[grid], OrderType.BUY_LIMIT, amount)

    def create_sell_order(self, grid):
        assert self.orders[grid] is None
        price = self.grids[grid]
        if self.transaction_strategy == 'even':
            amount = self.target_asset / (self.num_grids-grid+1)
        elif self.transaction_strategy == 'geom':
            amount = self.target_asset / self.geom_ratio
        else:
            raise NotImplementedError()
        self.orders[grid] = self.create_order(price, OrderType.SELL_LIMIT, amount)

    def confirm_order_finished(self, grid):
        order = self.trader.get_order(self.orders[grid])
        if order.state != OrderState.FILLED:
            if self.enable_logger:
                self.logger.error('Unfinished order detected')
            else:
                raise RuntimeError('Unfinished order detected')
        elif self.enable_logger:
            self.logger.info(f'Finished order confirmed. Order type: {order.type}; price: {order.price}; amount: {order.filled_amount}')
        if order.type == OrderType.BUY_LIMIT:
            self.target_asset += float(order.filled_amount) - float(order.filled_fees)
            self.base_asset -= float(order.filled_cash_amount)
        elif order.type == OrderType.SELL_LIMIT:
            self.target_asset -= float(order.filled_amount)
            self.base_asset += float(order.filled_cash_amount) - float(order.filled_fees)
        self.trader.cancel_orders(self.symbol, [order for order in self.orders if order is not None])
        self.orders = [None] * len(self.grids)

    def feed(self, price):
        self.newest_price = price
        curr_grid = self.get_newest_grid()
        if curr_grid > self.prev_grid:
            if self.prev_move != GridStrategy.DOWN:
                self.confirm_order_finished(self.prev_grid)
                if curr_grid <= self.num_grids:
                    self.create_sell_order(curr_grid)
                if curr_grid - 2 >= 0 and self.orders[curr_grid - 2] is None:
                    self.create_buy_order(curr_grid - 2)
            self.prev_move = GridStrategy.UP
        elif curr_grid < self.prev_grid:
            if self.prev_move != GridStrategy.UP:
                self.confirm_order_finished(self.prev_grid - 1)
                if curr_grid - 1 >= 0:
                    self.create_buy_order(curr_grid - 1)
                if curr_grid + 1 <= self.num_grids and self.orders[curr_grid + 1] is None:
                    self.create_sell_order(curr_grid + 1)
            self.prev_move = GridStrategy.DOWN
        self.prev_grid = curr_grid

    def start(self, price):
        self.start_time = datetime.now()
        if self.enable_logger:
            self.logger.info('Grid strategy started')
        self.newest_price = price
        if self.upper_price <= self.newest_price or self.lower_price >= self.newest_price:
            raise RuntimeError('Unable to start a transaction because the current price is beyond the range')

        curr_grid = self.get_newest_grid()
        self.create_initial_order(curr_grid)
        self.prev_grid = curr_grid

    def run(self):
        pass

    def stop(self):
        pass
