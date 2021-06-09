import math

import numpy as np

from huobi.constant import *

from strategy.single_pair_strategy import SinglePairStrategy
from strategy.runnable_strategy import RunnableStrategy
import utils


class BollingerTrackerStrategy(SinglePairStrategy, RunnableStrategy):
    def __init__(self, trader, symbol, target_asset, base_asset,
                 window_size=20, window_type=CandlestickInterval.MIN15, min_order_amount=50,
                 lower_std_scale=1.5, upper_std_scale=2.2, price_modifier=1.01,
                 enable_logger=True, root_dir=None, interval=300, trigger_interval=600):
        SinglePairStrategy.__init__(self, trader, symbol, target_asset, base_asset,
                                    enable_logger=enable_logger, root_dir=root_dir)
        RunnableStrategy.__init__(self, interval=interval)
        self.aggr = utils.StreamAggr(window_size * utils.get_seconds_of_candlestick_interval(window_type))
        self.window_size = window_size
        self.window_type = window_type
        self.min_order_amount = min_order_amount
        self.lower_std_scale = lower_std_scale
        self.upper_std_scale = upper_std_scale
        self.price_modifier = price_modifier
        self.buy_orders = []
        self.sell_orders = []
        self.trigger_interval = trigger_interval
        self.last_triggered = 0
        self.subscription = None

    def generate_orders(self, lower_price, upper_price, order_type):
        target_asset, base_asset = self.trader.get_balance_pair(self.symbol)
        if order_type == OrderType.BUY_LIMIT:
            asset = base_asset
            num_orders = math.floor(asset * 2 / (lower_price + upper_price) / self.min_order_amount * lower_price)
            amount = 0 if num_orders <= 0 else asset * 2 / (lower_price + upper_price) / num_orders
        elif order_type == OrderType.SELL_LIMIT:
            asset = target_asset
            num_orders = math.floor(asset * lower_price / self.min_order_amount)
            amount = 0 if num_orders <= 0 else asset / num_orders
        else:
            raise NotImplementedError()
        if num_orders <= 0:
            return []
        prices = np.linspace(lower_price, upper_price, num_orders)
        return self.trader.submit_orders(self.symbol, prices, amounts=[amount] * num_orders, order_type=order_type)

    def set_orders(self):
        if self.buy_orders:
            self.trader.cancel_orders(self.symbol, self.buy_orders)
        if self.sell_orders:
            self.trader.cancel_orders(self.symbol, self.sell_orders)
        ma = self.aggr.avg()
        std = self.aggr.std()
        lower_buy_price = ma - std * self.upper_std_scale
        upper_buy_price = ma - std * self.lower_std_scale
        if upper_buy_price >= self.newest_price:
            upper_buy_price = self.newest_price / self.price_modifier
        self.buy_orders = self.generate_orders(lower_buy_price, upper_buy_price, OrderType.BUY_LIMIT)
        lower_sell_price = ma + std * self.lower_std_scale
        upper_sell_price = ma + std * self.upper_std_scale
        if lower_sell_price <= self.newest_price:
            lower_sell_price = self.newest_price * self.price_modifier
        self.sell_orders = self.generate_orders(lower_sell_price, upper_sell_price, OrderType.SELL_LIMIT)

    def feed(self, price):
        self.newest_price = price
        self.aggr.feed(self.trader.get_time(), price)
        time = self.trader.get_time()
        if time - self.last_triggered >= self.trigger_interval:
            self.set_orders()
            self.last_triggered = time

    def start_impl(self, price):
        self.newest_price = price
        self.trader.add_trade_clearing_subscription(self.symbol, self.handle_trade_clear)
        for timestamp, price in self.trader.get_previous_prices(self.symbol, self.window_type, self.window_size):
            self.aggr.feed(timestamp=timestamp, value=price)
        self.set_orders()
        self.last_triggered = self.trader.get_time()

    def stop(self):
        self.trader.remove_trade_clearing_subscription(self.subscription)
        self.trader.cancel_orders(self.buy_orders)
        self.trader.cancel_orders(self.sell_orders)
        super().stop()
