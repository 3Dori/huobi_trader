from trader import BacktestTrader
from huobi.constant import *

import unittest


class BacktestTraderTest(unittest.TestCase):
    def test_create_order(self):
        symbol = 'ethusdt'
        trader = BacktestTrader({'usdt': 100, 'eth': 0.1}, {symbol: 2000})
        self.assertRaises(RuntimeError, trader.create_order, symbol, 1999, OrderType.BUY_LIMIT, 0.5)
        self.assertRaises(RuntimeError, trader.create_order, symbol, None, OrderType.BUY_MARKET, 2001)
        self.assertRaises(RuntimeError, trader.create_order, symbol, 2001, OrderType.SELL_LIMIT, 0.2)
        self.assertRaises(RuntimeError, trader.create_order, symbol, None, OrderType.SELL_MARKET, 0.2)
        self.assertRaises(ValueError, trader.create_order, symbol, 1999, OrderType.BUY_LIMIT, 0.0)
        self.assertRaises(TypeError, trader.create_order, symbol, None, OrderType.BUY_LIMIT, 0.01)
        trader.create_order(symbol, None, OrderType.BUY_MARKET, 90)
        self.assertAlmostEqual(trader.get_balance('usdt'), 10, 3)
        self.assertAlmostEqual(trader.get_balance('eth'), 90 / 2000 + 0.1, 3)

    def test_submit_order(self):
        symbol = 'ethusdt'
        trader = BacktestTrader({'usdt': 100, 'eth': 0.1}, {symbol: 2000})
        # buy
        trader.submit_orders(symbol, [1900, 1800], [0.02, 0.01], OrderType.BUY_LIMIT)
        trader.feed({symbol: 1850})
        self.assertAlmostEqual(trader.get_balance('eth'), 0.12, 3)
        trader.feed({symbol: 1860})
        self.assertAlmostEqual(trader.get_balance('eth'), 0.12, 3)
        trader.feed({symbol: 1750})
        self.assertAlmostEqual(trader.get_balance('eth'), 0.13, 3)
        # sell
        trader.submit_orders(symbol, [1900, 2000], [0.02, 0.01], OrderType.SELL_LIMIT)
        trader.feed({symbol: 1950})
        self.assertAlmostEqual(trader.get_balance('eth'), 0.11, 3)
        trader.feed({symbol: 2050})
        self.assertAlmostEqual(trader.get_balance('eth'), 0.10, 3)


    def test_feed(self):
        symbol = 'ethusdt'
        trader = BacktestTrader({'usdt': 100, 'eth': 0.1}, {symbol: 2000})
        order_id = trader.create_order(symbol, 1900, OrderType.BUY_LIMIT, 0.01)
        trader.feed({symbol: 1950})
        order = trader.get_order(order_id)
        self.assertTrue(order.state == OrderState.SUBMITTED)

        trader.feed({symbol: 1800})
        order = trader.get_order(order_id)
        self.assertTrue(order.state == OrderState.FILLED)

    def test_cancel(self):
        symbol = 'ethusdt'
        trader = BacktestTrader({'usdt': 100, 'eth': 0.1}, {symbol: 2000})
        order_id = trader.create_order(symbol, 1900, OrderType.BUY_LIMIT, 0.01)
        trader.feed({symbol: 1800})
        self.assertRaises(RuntimeError, trader.cancel_orders, symbol, [order_id])
