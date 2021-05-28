from constants import *
from base_trader import BaseTrader

from huobi.constant import *

import uuid


class BackTestOrder(object):
    def __init__(self, order_id, symbol, order_type, price, amount):
        self.id = order_id
        self.symbol = symbol
        self.type = order_type
        self.price = price
        self.amount = amount
        self.finished_at = 0 if order_type in (OrderType.BUY_LIMIT, OrderType.SELL_LIMIT) else 1
        self.canceled_at = 0
        self.state = OrderState.SUBMITTED


class BacktestTrader(BaseTrader):
    def __init__(self, balance):
        super().__init__()
        self.balance = {}
        self.newest_prices = {}
        self.orders = {}
        self.unfinished_orders = {}

    def get_balance(self, symbol='usdt'):
        return self.balance[symbol]

    def get_balance_pair(self, symbol):
        pair = transaction_pairs[symbol]
        return self.balance[pair.target], self.balance[pair.base]

    def get_newest_price(self, symbol):
        return self.newest_prices[symbol]

    def get_order(self, order_id):
        return self.orders[order_id]

    def create_order(self, symbol, price, order_type, amount=None, amount_fraction=None):
        pair = transaction_pairs[symbol]
        if order_type in (OrderType.BUY_MARKET, OrderType.SELL_MARKET):
            price = self.get_newest_price(symbol)
        if order_type in (OrderType.BUY_MARKET, OrderType.BUY_LIMIT):
            balance = self.get_balance(pair.base)
            if amount is None and amount_fraction is not None:
                amount = balance / price * amount_fraction
            if amount * price < balance:
                raise RuntimeError('Insufficient balance to buy')
        elif order_type in (OrderType.SELL_MARKET, OrderType.SELL_LIMIT):
            balance = self.get_balance(pair.target)
            if amount is None and amount_fraction is not None:
                amount = balance * amount_fraction
            if amount < balance:
                raise RuntimeError('Insufficient balance to sell')
        if order_type == OrderType.BUY_MARKET:
            self.balance[pair.target] += amount * (1 - BaseTrader.FEE)
            self.balance[pair.base] -= amount * price
        elif order_type == OrderType.SELL_MARKET:
            self.balance[pair.target] -= amount
            self.balance[pair.base] += amount * price * (1 - BaseTrader.FEE)

        order_id = str(uuid.uuid4())
        order = BackTestOrder(order_id, symbol, order_type, price, amount)
        if order_type in (OrderType.BUY_LIMIT, OrderType.SELL_LIMIT):
            self.unfinished_orders[order_id] = order
        self.orders[order_id] = order
        return order_id

    def cancel_orders(self, symbol, order_ids):
        for order_id in order_ids:
            order = self.unfinished_orders.get(order_id, None)
            if order is not None:
                del self.unfinished_orders[order_id]
            order = self.orders.get(order_id, None)
            if order is not None:
                order.state = OrderState.CANCELED

    def feed(self, symbol, price):
        self.newest_prices[symbol] = price
        finished_order_ids = []
        pair = transaction_pairs[symbol]
        for order_id, order in self.unfinished_orders:
            if symbol == order.symbol:
                assert order.type in (OrderType.BUY_LIMIT, OrderType.SELL_LIMIT)
                if order.type == OrderType.BUY_LIMIT and price <= order.price:
                    self.balance[pair.target] += order.amount * (1 - BaseTrader.FEE)
                    self.balance[pair.base] -= order.amount * price
                    finished_order_ids.append(order_id)
                elif order.type == OrderType.SELL_LIMIT and price >= order.price:
                    self.balance[pair.target] -= order.amount
                    self.balance[pair.base] += order.amount * price * (1 - BaseTrader.FEE)
                    finished_order_ids.append(order_id)
        for order_id in finished_order_ids:
            del self.unfinished_orders[order_id]
