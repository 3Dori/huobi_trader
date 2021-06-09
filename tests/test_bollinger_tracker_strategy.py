import unittest

import matplotlib.pyplot as plt
import numpy as np

from huobi.constant import *

from trader import BacktestTrader
from strategy.bollinger_tracker_strategy import BollingerTrackerStrategy
import utils


def basic_monte_carlo_bollinger_tracker_strategy(seed=None):
    if seed is not None:
        np.random.seed(seed)
    init_price = 2800
    prices = utils.brownian_motion(init_price, 10000, 0.1, sigma=5)
    usdt = 1000
    eth = 0
    trader = BacktestTrader({'usdt': usdt, 'eth': eth}, {'ethusdt': prices[0]})
    strategy = BollingerTrackerStrategy(trader, 'ethusdt', eth, usdt,
                                        window_size=10, window_type=CandlestickInterval.MIN15,
                                        enable_logger=False, interval=None, trigger_interval=1800)
    strategy.start(prices[0])
    original_asset = strategy.get_total_asset(in_base=True)
    for i, price in enumerate(prices[1:]):
        trader.feed({'ethusdt': price})
        strategy.feed(price)
    hold_asset = original_asset * prices[-1] / prices[0]
    strategy_asset = strategy.get_total_asset(in_base=True)
    return prices[-1], hold_asset, strategy_asset


def monte_carlo_bollinger_tracker_strategy(sims=200):
    prices, hold_assets, strategy_assets = [], [], []
    for sim in range(sims):
        try:
            price, hold_asset, strategy_asset = basic_monte_carlo_bollinger_tracker_strategy(seed=sim)
            prices.append(price)
            hold_assets.append(hold_asset)
            strategy_assets.append(strategy_asset)
        except:
            print(sim)
    plt.plot(prices, hold_assets)
    plt.scatter(prices, strategy_assets)
    plt.show()
    print(np.mean(strategy_assets))


def vis_trading(seed=None):
    if seed is not None:
        np.random.seed(seed)
    init_price = 2800
    prices = utils.brownian_motion(init_price, 10000, 0.1, sigma=5)
    usdt = 1000
    eth = 0
    trader = BacktestTrader({'usdt': usdt, 'eth': eth}, {'ethusdt': prices[0]})
    strategy = BollingerTrackerStrategy(trader, 'ethusdt', eth, usdt,
                                        window_size=10, window_type=CandlestickInterval.MIN15,
                                        enable_logger=False, interval=None, trigger_interval=1800)
    last_buy_orders = strategy.buy_orders
    last_sell_orders = strategy.sell_orders
    strategy.start(prices[0])
    buy_orders_time = []
    buy_orders_history = []
    sell_orders_time = []
    sell_orders_history = []
    for i, price in enumerate(prices[1:]):
        trader.feed({'ethusdt': price})
        strategy.feed(price)
        if strategy.buy_orders is not last_buy_orders:
            last_buy_orders = strategy.buy_orders
            for order_id in last_buy_orders:
                buy_orders_time.append(i)
                buy_orders_history.append(trader.get_order(order_id).price)
        if strategy.sell_orders is not last_sell_orders:
            last_sell_orders = strategy.sell_orders
            for order_id in last_sell_orders:
                sell_orders_time.append(i)
                sell_orders_history.append(trader.get_order(order_id).price)
    plt.plot(prices)
    plt.scatter(buy_orders_time, buy_orders_history, color='red')
    plt.scatter(sell_orders_time, sell_orders_history, color='green')
    plt.show()
    print(strategy.get_total_asset(in_base=True))


if __name__ == '__main__':
    # monte_carlo_bollinger_tracker_strategy()
    basic_monte_carlo_bollinger_tracker_strategy(95)
    # vis_trading(1)
