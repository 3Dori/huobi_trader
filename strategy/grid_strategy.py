import warnings

import numpy as np

from huobi.constant import *

from constants import *
from trader import BaseTrader


class GridStrategy(object):
    STAY = 0
    UP = 1
    DOWN = -1

    def __init__(self, trader: BaseTrader, symbol, target_asset, base_asset, lower_price, upper_price, num_grids,
                 newest_price, grid_type='arithmetic'):
        self.trader = trader
        self.symbol = symbol
        target_balance, base_balance = self.trader.get_balance_pair(symbol)
        if target_balance < target_asset:
            raise RuntimeError(f'Insufficient balance for {self.target_symbol}')
        if base_balance < target_asset:
            raise RuntimeError(f'Insufficient balance for {self.base_symbol}')
        self.target_asset = target_asset
        self.base_asset = base_asset
        self.newest_price = newest_price

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
        self.orders = [None] * len(self.grids)

        if upper_price <= self.newest_price or lower_price >= self.newest_price:
            raise RuntimeError('Unable to start a transaction because the current price is beyond the range')
        curr_grid = self.get_newest_grid()
        self.initial_total_asset_in_base, self.initial_total_asset_in_target = self.get_total_asset()
        self.create_initial_order(curr_grid)
        self.prev_grid = curr_grid
        self.prev_move = GridStrategy.STAY    # Record the moving trend of the price

    @property
    def base_symbol(self):
        return transaction_pairs[self.symbol].base

    @property
    def target_symbol(self):
        return transaction_pairs[self.symbol].target

    def get_total_asset(self, in_base=False):
        total_asset_in_base = self.base_asset + self.target_asset * self.newest_price
        total_asset_in_target = total_asset_in_base / self.newest_price
        if in_base:
            return total_asset_in_base
        else:
            return total_asset_in_base, total_asset_in_target

    def create_initial_order(self, curr_grid):
        assumed_asset = self.initial_total_asset_in_base * curr_grid / (self.num_grids + 1)
        if assumed_asset > self.base_asset:
            diff = assumed_asset - self.base_asset
            amount = diff / self.newest_price
            try:
                self.create_order(None, OrderType.SELL_MARKET, amount)
            except RuntimeError:
                warnings.warn('Unable to create initial order')
        elif assumed_asset < self.base_asset:
            diff = self.base_asset - assumed_asset
            amount = diff / self.newest_price
            try:
                self.create_order(None, OrderType.BUY_MARKET, amount)
            except RuntimeError:
                warnings.warn('Unable to create initial order')
        if curr_grid - 1 >= 0:
            self.create_buy_order(curr_grid - 1)    # create initial buy limit order
        if curr_grid <= self.num_grids:
            self.create_sell_order(curr_grid)    # create initial sell limit order

    def get_newest_grid(self):
        return np.searchsorted(self.grids, self.newest_price)

    def create_order(self, price, order_type, amount=None, amount_fraction=None):
        try:
            return self.trader.create_order(self.symbol, price, order_type, amount, amount_fraction)
        except Exception as e:
            raise RuntimeError(f'Unable to create order: {e.args[0]}')

    def create_buy_order(self, grid):
        assert self.orders[grid] is None
        # balance = self.trader.get_balance(self.base_symbol) TODO
        amount = self.initial_total_asset_in_base / self.num_grids / self.newest_price
        self.orders[grid] = self.create_order(self.grids[grid], OrderType.BUY_LIMIT, amount)

    def create_sell_order(self, grid):
        assert self.orders[grid] is None
        amount = self.initial_total_asset_in_target / self.num_grids
        self.orders[grid] = self.create_order(self.grids[grid], OrderType.SELL_LIMIT, amount)

    def confirm_order_finished(self, grid):
        order = self.trader.get_order(self.orders[grid])
        if order.state != OrderState.FILLED:
            raise RuntimeError('Unexpected unfinished order')
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
                self.create_buy_order(curr_grid - 1)
                if curr_grid + 1 <= self.num_grids and self.orders[curr_grid + 1] is None:
                    self.create_sell_order(curr_grid + 1)
            self.prev_move = GridStrategy.DOWN
        self.prev_grid = curr_grid

    def run(self):
        pass

    def stop(self):
        pass
