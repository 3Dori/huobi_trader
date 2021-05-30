import unittest

import matplotlib.pyplot as plt
import numpy as np

from trader import BacktestTrader
from strategy.grid_strategy import GridStrategy
from utils.market_simulator import brownian_motion


root_dir = '/Users/clyx/Documents/quant/order_queue'


class GridStrategyTester(unittest.TestCase):
    def test_grid_strategy(self):
        def feed_price_and_assert(price, prev_grid, active_grids):
            trader.feed({'ethusdt': price})
            strategy.feed(price)
            self.assertEqual(strategy.prev_grid, prev_grid)
            for grid, order in enumerate(strategy.orders):
                if grid in active_grids:
                    self.assertIsNotNone(order)
                else:
                    self.assertIsNone(order)
            self.assertAlmostEqual(strategy.base_asset, trader.balance['usdt'])
            self.assertAlmostEqual(strategy.target_asset, trader.balance['eth'])

        prices = [2501, 2510, 2610, 2710, 2610, 2710, 2610, 2510]
        usdt = 1000
        eth = 0.4
        trader = BacktestTrader({'usdt': usdt, 'eth': eth}, {'ethusdt': prices[0]})
        strategy = GridStrategy(trader, 'ethusdt', eth, usdt, 2000, 3000, 11, enable_logger=False)
        strategy.start(prices[0])
        feed_price_and_assert(prices[1], 6, [5, 6])    # 2501 -> 2510
        feed_price_and_assert(prices[2], 7, [5, 7])      # 2510 -> 2610
        feed_price_and_assert(prices[3], 8, [6, 8])      # 2610 -> 2710
        feed_price_and_assert(prices[4], 7, [6, 8])    # 2710 -> 2610
        feed_price_and_assert(prices[5], 8, [6, 8])      # 2610 -> 2710
        feed_price_and_assert(prices[6], 7, [6, 8])    # 2710 -> 2610
        feed_price_and_assert(prices[7], 6, [5, 7])    # 2610 -> 2510

    def test_grid_strategy_overflow(self):
        prices = [2501, 2610, 2710, 2810, 2910, 3010, 3110]
        usdt = 1000
        eth = 0.4
        trader = BacktestTrader({'usdt': usdt, 'eth': eth}, {'ethusdt': prices[0]})
        strategy = GridStrategy(trader, 'ethusdt', eth, usdt, 2000, 3000, 11, enable_logger=False)
        strategy.start(prices[0])
        for price in prices[1:]:
            trader.feed({'ethusdt': price})
            strategy.feed(price)
        self.assertAlmostEqual(trader.balance['eth'], 0.0)


def basic_backtest_grid_strategy(seed=None):
    if seed is not None:
        np.random.seed(seed)
    init_price = 2800
    prices = brownian_motion(init_price, 10000, 0.1, sigma=5)
    usdt = 1000
    eth = 0.2
    original_asset = usdt + eth * init_price
    trader = BacktestTrader({'usdt': usdt, 'eth': eth}, {'ethusdt': prices[0]})
    strategy = GridStrategy(trader, 'ethusdt', eth, usdt, 2500, 3000, 19,
                            transaction_strategy='even', geom_ratio=4, enable_logger=False)
    strategy.start(prices[0])
    for i, price in enumerate(prices[1:]):
        try:
            trader.feed({'ethusdt': price})
            strategy.feed(price)
        except:
            print(i)
            raise
    hold_asset = original_asset * prices[-1] / prices[0]
    strategy_asset = strategy.get_total_asset(in_base=True)
    return prices[-1], hold_asset, strategy_asset


def backtest_grid_strategy(sims=200):
    prices, hold_assets, strategy_assets = [], [], []
    for sim in range(sims):
        try:
            price, hold_asset, strategy_asset = basic_backtest_grid_strategy(seed=sim)
            if price <= 2780 or price >= 2820:
                continue
            prices.append(price)
            hold_assets.append(hold_asset)
            strategy_assets.append(strategy_asset)
        except:
            print(sim)
    plt.plot(prices, hold_assets)
    plt.scatter(prices, strategy_assets)
    plt.show()
    print(np.mean(strategy_assets))
    # basic_backtest_grid_strategy(109)


if __name__ == '__main__':
    backtest_grid_strategy()

