from constants import *
from .base_trader import BaseTrader

from huobi.constant import *

import numpy as np

import uuid


class BackTestOrder(object):
    def __init__(self, order_id, symbol, order_type, price, amount):
        self.id = order_id
        self.symbol = symbol
        self.type = order_type
        self.price = price
        self.amount = amount
        self.filled_amount = 0
        self.filled_fees = 0
        self.filled_cash_amount = 0
        self.finished_at = 0
        self.canceled_at = 0
        self.state = OrderState.SUBMITTED
        if order_type == OrderType.BUY_MARKET:
            self.set_finished(amount, amount * BaseTrader.FEE * 2, amount * price)
        elif order_type == OrderType.SELL_MARKET:
            self.set_finished(amount, amount * price * BaseTrader.FEE * 2, amount * price)

    def set_finished(self, filled_amount, filled_fees, filled_cash_amount):
        self.finished_at = 1
        self.filled_amount = filled_amount
        self.filled_fees = filled_fees
        self.filled_cash_amount = filled_cash_amount
        self.state = OrderState.FILLED


class BacktestTrader(BaseTrader):
    def __init__(self, balance, init_price):
        super().__init__()
        self.balance = balance
        self.newest_prices = init_price
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

    @staticmethod
    def correct_amount(amount, symbol):
        scale = transaction_pairs[symbol].amount_scale
        return amount - 10 ** -scale

    def create_order(self, symbol, price, order_type, amount=None, amount_fraction=None):
        pair = transaction_pairs[symbol]
        if order_type in (OrderType.BUY_MARKET, OrderType.SELL_MARKET):
            price = self.get_newest_price(symbol)
        if order_type in (OrderType.BUY_MARKET, OrderType.BUY_LIMIT):
            balance = self.get_balance(pair.base)
            if amount is None and amount_fraction is not None:
                amount = balance / price * amount_fraction
            amount = self.correct_amount(amount, symbol)
            if amount * price > balance:
                raise RuntimeError(f'Insufficient balance to buy: buying {amount * price}, remaining: {balance}')
        elif order_type in (OrderType.SELL_MARKET, OrderType.SELL_LIMIT):
            balance = self.get_balance(pair.target)
            if amount is None and amount_fraction is not None:
                amount = balance * amount_fraction
            amount = self.correct_amount(amount, symbol)
            if amount > balance:
                raise RuntimeError(f'Insufficient balance to sell: selling {amount}, remaining {balance}')
        if type(price) not in (float, int, np.float_):
            raise TypeError('price must be of float or int type')
        if order_type == OrderType.BUY_MARKET:
            self.balance[pair.target] += amount * (1 - BaseTrader.FEE * 2)
            self.balance[pair.base] -= amount * price
        elif order_type == OrderType.SELL_MARKET:
            self.balance[pair.target] -= amount
            self.balance[pair.base] += amount * price * (1 - BaseTrader.FEE * 2)

        order_id = str(uuid.uuid4())
        order = BackTestOrder(order_id, symbol, order_type, price, amount)
        if order_type in (OrderType.BUY_LIMIT, OrderType.SELL_LIMIT):
            self.unfinished_orders[order_id] = order
        self.orders[order_id] = order
        return order_id

    def cancel_orders(self, symbol, order_ids):
        for order_id in order_ids:
            order = self.unfinished_orders.get(order_id, None)
            if order is not None and order.symbol == symbol:
                assert order.state not in (OrderState.FILLED, OrderState.CANCELED)
                del self.unfinished_orders[order_id]
                order = self.orders.get(order_id, None)
                order.state = OrderState.CANCELED

    def feed(self, prices):
        for symbol, price in prices.items():
            self.newest_prices[symbol] = price
            finished_order_ids = []
            pair = transaction_pairs[symbol]
            for order_id, order in self.unfinished_orders.items():
                if symbol == order.symbol:
                    assert order.type in (OrderType.BUY_LIMIT, OrderType.SELL_LIMIT)
                    if order.type == OrderType.BUY_LIMIT and price <= order.price:
                        filled_cash_amount = order.amount * price
                        self.balance[pair.target] += order.amount * (1 - BaseTrader.FEE)
                        self.balance[pair.base] -= filled_cash_amount
                        finished_order_ids.append(order_id)
                        self.orders[order_id].set_finished(order.amount, order.amount * BaseTrader.FEE, filled_cash_amount)
                    elif order.type == OrderType.SELL_LIMIT and price >= order.price:
                        filled_cash_amount = order.amount * price
                        self.balance[pair.target] -= order.amount
                        self.balance[pair.base] += filled_cash_amount * (1 - BaseTrader.FEE)
                        finished_order_ids.append(order_id)
                        self.orders[order_id].set_finished(order.amount, filled_cash_amount * BaseTrader.FEE, filled_cash_amount)
            for order_id in finished_order_ids:
                del self.unfinished_orders[order_id]
