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
        self.assertRaises(TypeError, trader.create_order, symbol, None, OrderType.BUY_LIMIT, 0.01)
        trader.create_order(symbol, None, OrderType.BUY_MARKET, 90)
        self.assertAlmostEqual(trader.get_balance('usdt'), 10, 3)
        self.assertAlmostEqual(trader.get_balance('eth'), 90 / 2000 + 0.1, 3)

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
