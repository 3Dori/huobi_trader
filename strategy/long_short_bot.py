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
                 lower_profit=1.0, upper_profit=2.0, grid_type='geometric',
                 enable_logger=True, root_dir=None, interval=10):
        SinglePairStrategy.__init__(self, trader, symbol, target_asset, base_asset,
                                    enable_logger=enable_logger, root_dir=root_dir)
        RunnableStrategy.__init__(self, interval)
        self.window_size = window_size
        self.window_type = window_type
        window_range = window_size * utils.get_seconds_of_candlestick_interval(window_type)
        self.aggr = StreamAggr(window_range, window_type='s', metrics=['bollinger'])
        self.window_start = self.window_end = 0
        self.num_orders = num_orders
        if lower_profit >= upper_profit:
            raise ValueError('lower_profit must be smaller than upper_profit')
        if lower_profit <= trader.FEE * 2:
            raise ValueError(f'Profit is too small: {lower_profit}')
        if grid_type == 'arithmetic':
            self.profit_grids = np.linspace(lower_profit, upper_profit, num_orders)
        elif grid_type == 'geometric':
            self.profit_grids = np.geomspace(lower_profit, upper_profit, num_orders)
        else:
            raise ValueError(f'Unknown grid_type: {grid_type}')
        self.buy_orders = [None] * num_orders
        self.sell_orders = [None] * num_orders

    def feed(self, price):
        self.newest_price = price
        self.aggr.feed(timestamp=int(time.time()), value=price)
        ma = self.aggr.avg()
        std = self.aggr.std()

    def pre_start(self):
        pass

    def start(self, price=None):
        if price is None:
            price = self.trader.get_newest_price(self.symbol)
        self.newest_price = price
        # estimate ma and bollinger with mid point of previous candlesticks' open and close price
        candlesticks = self.trader.market_client.get_candlestick(self.symbol, self.window_type, self.window_size)
        candlesticks = sorted(candlesticks, key=lambda cs: cs.id)
        for candlestick in candlesticks:
            self.aggr.feed(timestamp=candlestick.id, value=(candlestick.open + candlestick.close) / 2)
        if self.interval is not None:
            self.pre_start()
            self.thread = threading.Thread(target=self.run, args=())
            self.thread.start()
        else:
            self.pre_start()
