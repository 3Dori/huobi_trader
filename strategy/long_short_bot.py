import time
import threading

import numpy as np

from huobi.constant import *

import utils
from trader import BaseTrader
from utils import StreamAggr
from .runnable_strategy import RunnableStrategy
from .single_pair_strategy import SinglePairStrategy


class LongShortBot(SinglePairStrategy, RunnableStrategy):
    def __init__(self, trader: BaseTrader, symbol, target_asset, base_asset,
                 window_size=20, window_type=CandlestickInterval.MIN1, num_orders=5,
                 lower_profit=0.01, upper_profit=0.02, grid_type='geometric',
                 enable_logger=True, root_dir=None, interval=10):
        SinglePairStrategy.__init__(self, trader, symbol, target_asset, base_asset,
                                    enable_logger=enable_logger, root_dir=root_dir)
        RunnableStrategy.__init__(self, interval)
        self.window_size = window_size
        self.window_type = window_type
        self.aggr = StreamAggr(window_size * utils.get_seconds_of_candlestick_interval(window_type))
        self.num_orders = num_orders
        if lower_profit >= upper_profit:
            raise ValueError('lower_profit must be smaller than upper_profit')
        if lower_profit <= trader.FEE * 2:
            raise ValueError(f'Profit is too small: {lower_profit}')
        if grid_type == 'arithmetic':
            self.profit_grids = np.linspace(lower_profit+1, upper_profit+1, num_orders)
        elif grid_type == 'geometric':
            self.profit_grids = np.geomspace(lower_profit+1, upper_profit+1, num_orders)
        else:
            raise ValueError(f'Unknown grid_type: {grid_type}')
        self.buy_order_ids = [None] * num_orders
        self.sell_order_ids = [None] * num_orders
        self.buy_order_ids_history = [[] for _ in range(num_orders)]
        self.sell_order_ids_history = [[] for _ in range(num_orders)]

    def confirm_and_create_reversed_orders(self, order_type, total_asset, bollinger_band):
        if order_type == OrderType.BUY_LIMIT:
            order_ids = self.buy_order_ids
            reversed_order_ids = self.sell_order_ids
            reversed_order_ids_history = self.sell_order_ids_history
            reversed_order_type = OrderType.SELL_LIMIT
        elif order_type == OrderType.SELL_LIMIT:
            order_ids = self.sell_order_ids
            reversed_order_ids = self.buy_order_ids
            reversed_order_ids_history = self.buy_order_ids_history
            reversed_order_type = OrderType.BUY_LIMIT
        else:
            raise RuntimeError(f'Unknown order_type: {order_type}')
        num_available_orders = 0
        finished_orders = []
        orders_to_be_canceled = []
        for level, order_id in enumerate(order_ids):
            if order_id is None:
                num_available_orders += 1
                finished_orders.append(None)
                continue
            order = self.trader.get_order(order_id)
            if order.state == OrderState.FILLED:
                num_available_orders += 1
                finished_orders.append(order)
                if reversed_order_ids[level] is not None:
                    orders_to_be_canceled.append(reversed_order_ids[level])
                    reversed_order_ids[level] = None
        self.cancel_orders(orders_to_be_canceled)
        for level, order in enumerate(finished_orders):
            if order is None:
                continue
            profit = self.profit_grids[level] + self.trader.FEE * 2
            assert order.state == OrderState.FILLED
            price = float(order.price)
            if reversed_order_type == OrderType.SELL_LIMIT:
                price = (bollinger_band + price * profit) / 2  # mean value of upper bollinger band and target profit
                amount = total_asset / num_available_orders
            else:
                price = (bollinger_band + price / profit) / 2  # mean value of upper bollinger band and target profit
                amount = total_asset / num_available_orders / price
            reversed_order_id = self.create_order(price, reversed_order_type, amount)
            reversed_order_ids[level] = reversed_order_id
            reversed_order_ids_history[level].append(reversed_order_id)

    def get_bollinger_band(self):
        ma = self.aggr.avg()
        std = self.aggr.std()
        return ma - std, ma + std

    def feed(self, price):
        self.newest_price = price
        self.aggr.feed(timestamp=self.trader.get_time(), value=price)
        lower_bollinger_band, upper_bollinger_band = self.get_bollinger_band()
        total_asset_in_base, total_asset_in_target = self.get_total_asset()
        self.confirm_and_create_reversed_orders(OrderType.BUY_LIMIT, total_asset_in_target, lower_bollinger_band)
        self.confirm_and_create_reversed_orders(OrderType.SELL_LIMIT, total_asset_in_base, upper_bollinger_band)

    def create_initial_orders(self, order_type, total_asset, reversed_bollinger_band):
        if order_type == OrderType.BUY_LIMIT:
            order_ids = self.buy_order_ids
        elif order_type == OrderType.SELL_LIMIT:
            order_ids = self.sell_order_ids
        else:
            raise RuntimeError(f'Unknown order_type: {order_type}')
        for level in range(self.num_orders):
            profit = self.profit_grids[level] + self.trader.FEE * 2
            if order_type == OrderType.SELL_LIMIT:
                price = reversed_bollinger_band * profit
                amount = total_asset / self.num_orders
            else:
                price = reversed_bollinger_band / profit
                amount = total_asset / self.num_orders / price
            order_ids[level] = self.create_order(price, order_type, amount)

    def pre_start(self, price):
        self.aggr.feed(timestamp=self.trader.get_time(), value=price)
        lower_bollinger_band, upper_bollinger_band = self.get_bollinger_band()
        total_asset_in_base, total_asset_in_target = self.get_total_asset()
        self.create_initial_orders(OrderType.BUY_LIMIT, total_asset_in_base, upper_bollinger_band)
        self.create_initial_orders(OrderType.SELL_LIMIT, total_asset_in_target, lower_bollinger_band)

    def start(self, price=None):
        if price is None:
            price = self.trader.get_newest_price(self.symbol)
        self.newest_price = price
        # estimate ma and bollinger with mid point of previous candlesticks' open and close price
        for timestamp, price in self.trader.get_previous_prices(self.symbol, self.window_type, self.window_size):
            self.aggr.feed(timestamp=timestamp, value=price)
        if self.interval is not None:
            self.pre_start(price)
            self.thread = threading.Thread(target=self.run, args=())
            self.thread.start()
        else:
            self.pre_start(price)
