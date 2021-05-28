from constants import *

from huobi.constant import *

import numpy as np


class GridStrategy(object):
    STAY = 0
    UP = 1
    DOWN = -1

    def __init__(self, trader, symbol, target_asset, base_asset, lower_price, upper_price, num_grids,
                 grid_type='arithmetic'):
        self.trader = trader
        self.symbol = symbol
        target_balance, base_balance = self.trader.get_balance_pair(symbol)
        if target_balance < target_asset:
            raise RuntimeError(f'Insufficient balance for {transaction_pairs[symbol].target}')
        if base_balance < target_asset:
            raise RuntimeError(f'Insufficient balance for {transaction_pairs[symbol].base}')
        self.target_asset = target_asset
        self.base_asset = base_asset

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

        newest_price = self.get_newest_price()
        if upper_price <= newest_price or lower_price >= newest_price:
            raise RuntimeError('Unable to start a transaction because the current price is beyond the range')
        curr_grid = self.get_newest_grid(newest_price)
        self.initial_total_asset_in_base, self.initial_total_asset_in_target = self.get_total_asset(newest_price)
        self.create_initial_order(curr_grid, newest_price)
        self.prev_grid = curr_grid
        self.prev_move = GridStrategy.STAY    # Record the moving trend of the price
        # self.back_test = False

    def get_newest_price(self):
        return self.trader.get_newest_price(self.symbol)

    def get_total_asset(self, newest_price=None):
        newest_price = newest_price or self.get_newest_price()
        total_asset_in_base = self.base_asset + self.target_asset * newest_price
        total_asset_in_target = total_asset_in_base / newest_price
        return total_asset_in_base, total_asset_in_target

    def create_initial_order(self, curr_grid, newest_price):
        assumed_asset = self.initial_total_asset_in_base * curr_grid / (self.num_grids + 1)
        if assumed_asset > self.initial_total_asset_in_base:
            diff = assumed_asset - self.initial_total_asset_in_base
            amount = diff / newest_price
            self.create_order(None, OrderType.SELL_MARKET, amount)
        elif assumed_asset < self.initial_total_asset_in_base:
            diff = self.initial_total_asset_in_base - assumed_asset
            amount = diff / newest_price
            self.create_order(None, OrderType.BUY_MARKET, amount)
        if curr_grid - 1 >= 0:
            self.create_buy_order(curr_grid - 1, newest_price)    # create initial buy limit order
        if curr_grid + 1 <= self.num_grids:
            self.create_sell_order(curr_grid + 1)    # create initial sell limit order

    def get_newest_grid(self, newest_price=None):
        newest_price = newest_price or self.get_newest_price()
        return np.searchsorted(self.grids, newest_price)

    def create_order(self, price, order_type, amount=None, amount_fraction=None):
        try:
            return self.trader.create_order(self.symbol, price, order_type, amount, amount_fraction)
        except Exception as e:
            raise RuntimeError(f'Unable to create initial order: {e.args[0]}')

    def create_buy_order(self, grid, newest_price=None):
        assert self.orders[grid] is None
        newest_price = newest_price or self.get_newest_price()
        amount = self.initial_total_asset_in_base / self.num_grids / newest_price
        self.orders[grid] = self.create_order(self.grids[grid], OrderType.BUY_LIMIT, amount)

    def create_sell_order(self, grid):
        assert self.orders[grid] is None
        amount = self.initial_total_asset_in_target / self.num_grids
        self.orders[grid] = self.create_order(self.grids[grid], OrderType.BUY_LIMIT, amount)

    def confirm_order_finished(self, grid):
        order = self.trader.get_order(self.orders[grid])
        if order.finished_at != 0:
            raise RuntimeError('Unexpected unfinished order')
        self.orders[grid] = None

    def feed(self):
        newest_price = self.get_newest_price()
        curr_grid = self.get_newest_grid(newest_price)
        if curr_grid > self.prev_grid and self.prev_move != GridStrategy.DOWN:
            self.confirm_order_finished(self.prev_grid)
            self.create_sell_order(curr_grid)
            if curr_grid - 2 >= 0 and self.grids[curr_grid - 2] is None:
                self.create_buy_order(curr_grid - 2)
            self.prev_move = GridStrategy.DOWN
        elif curr_grid < self.prev_grid and self.prev_move != GridStrategy.UP:
            self.confirm_order_finished(self.prev_grid)
            self.create_buy_order(curr_grid, newest_price)
            if curr_grid + 2 <= self.num_grids and self.grids[curr_grid + 2] is None:
                self.create_sell_order(curr_grid - 2)
            self.prev_move = GridStrategy.UP
        self.prev_grid = curr_grid

    def run(self):
        pass

    def stop(self):
        pass
