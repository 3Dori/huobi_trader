import uuid

import numpy as np

from huobi.constant import *

from constants import *
from .base_trader import BaseTrader
import utils


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
            self.set_finished(amount / price, amount / price * BaseTrader.FEE * 2, amount)
        elif order_type == OrderType.SELL_MARKET:
            self.set_finished(amount, amount * price * BaseTrader.FEE * 2, amount * price)

    def set_finished(self, filled_amount, filled_fees, filled_cash_amount):
        self.finished_at = 1
        self.filled_amount = filled_amount
        self.filled_fees = filled_fees
        self.filled_cash_amount = filled_cash_amount
        self.state = OrderState.FILLED


class BackTestSubscription(object):
    def __init__(self, callback, error_handler):
        self.callback = callback
        self.error_handler = error_handler

    def notify(self, trade_clearing_event):
        self.callback(trade_clearing_event)


class BacktestTrader(BaseTrader):
    def __init__(self, balance, init_price, init_time=10000000):
        super().__init__()
        self.balance = balance
        self.init_price = init_price
        self.init_time = init_time
        self.time = init_time
        self.newest_prices = init_price
        self.orders = {}
        self.unfinished_orders = {}
        self.subscriptions = []

    def add_trader_clearing_subscription(self, symbol, callback, error_handler=None):
        subscription = BackTestSubscription(callback, error_handler)
        self.subscriptions.append(subscription)
        return subscription

    def remove_trader_clearing_subscription(self, subscription):
        self.subscriptions.remove(subscription)

    def get_balance(self, symbol='usdt'):
        return self.balance[symbol]

    def get_balance_pair(self, symbol):
        pair = transaction_pairs[symbol]
        return self.balance[pair.target], self.balance[pair.base]

    def get_newest_price(self, symbol):
        return self.newest_prices[symbol]

    def get_order(self, order_id):
        return self.orders[order_id]

    def notify_all_subscriptions(self, order):
        from huobi.model.trade import TradeClearing, TradeClearingEvent
        trade_clearing = TradeClearing()
        trade_clearing.symbol = order.symbol
        trade_clearing.orderId = order.id
        trade_clearing.tradePrice = order.price
        trade_clearing.tradeVolume = order.filled_amount
        trade_clearing.transactFee = order.filled_fees
        trade_clearing.orderType = order.type
        trade_clearing_event = TradeClearingEvent()
        trade_clearing_event.data = trade_clearing
        for subscription in self.subscriptions:
            subscription.notify(trade_clearing_event)

    def create_order(self, symbol, price, order_type, amount=None, amount_fraction=None):
        pair = transaction_pairs[symbol]
        if order_type in (OrderType.BUY_MARKET, OrderType.SELL_MARKET):
            price = self.get_newest_price(symbol)
        if order_type == OrderType.BUY_LIMIT:
            balance = self.get_balance(pair.base)
            if amount is None and amount_fraction is not None:
                amount = balance / price * amount_fraction
            amount = self.correct_amount(amount, symbol)
            if amount * price > balance:
                raise RuntimeError(f'Insufficient balance to buy: buying {amount * price}, remaining: {balance}')
        if order_type == OrderType.BUY_MARKET:
            balance = self.get_balance(pair.base)
            if amount is None and amount_fraction is not None:
                amount = balance
            amount = self.correct_amount(amount, symbol)
            if amount > balance:
                raise RuntimeError(f'Insufficient balance to buy: buying {amount}, remaining: {balance}')
        elif order_type in (OrderType.SELL_MARKET, OrderType.SELL_LIMIT):
            balance = self.get_balance(pair.target)
            if amount is None and amount_fraction is not None:
                amount = balance * amount_fraction
            amount = self.correct_amount(amount, symbol)
            if amount > balance:
                raise RuntimeError(f'Insufficient balance to sell: selling {amount}, remaining {balance}')
        if type(price) not in (float, int, np.float_):
            raise TypeError('price must be of float or int type')
        if amount <= 0:
            raise ValueError('amount must be greater than 0')
        if order_type == OrderType.BUY_MARKET:
            self.balance[pair.target] += amount / price * (1 - self.FEE * 2)
            self.balance[pair.base] -= amount
        elif order_type == OrderType.SELL_MARKET:
            self.balance[pair.target] -= amount
            self.balance[pair.base] += amount * price * (1 - self.FEE * 2)

        order_id = str(uuid.uuid4())
        order = BackTestOrder(order_id, symbol, order_type, price, amount)
        if order_type in (OrderType.BUY_LIMIT, OrderType.SELL_LIMIT):
            self.unfinished_orders[order_id] = order
        elif order_type in (OrderType.BUY_MARKET, OrderType.SELL_MARKET):
            self.notify_all_subscriptions(order)
        self.orders[order_id] = order
        return order_id

    def submit_orders(self, symbol, prices, amounts, order_type):
        orders = [
            self.create_order(symbol, price, order_type, amount)
            for price, amount in zip(prices, amounts)
        ]
        return orders

    def cancel_orders(self, symbol, order_ids):
        for order_id in order_ids:
            order = self.orders.get(order_id, None)
            if order is None:
                raise RuntimeError(f'Order does not exist: {order_id}')
            if order_id not in self.unfinished_orders:
                pass
            if order.symbol == symbol:
                if self.unfinished_orders.get(order_id):
                    del self.unfinished_orders[order_id]
                    order = self.orders.get(order_id, None)
                    order.state = OrderState.CANCELED

    def get_time(self):
        self.time += 1
        return self.time

    def get_previous_prices(self, symbol, window_type, window_size):
        seconds = utils.get_seconds_of_candlestick_interval(window_type)
        prices = utils.brownian_motion(self.init_price[symbol], window_size, delta_t=0.1 * seconds)
        return zip(range(self.init_time - window_size * seconds, self.init_time, seconds), reversed(prices))

    def feed(self, prices):
        for symbol, price in prices.items():
            self.newest_prices[symbol] = price
            finished_order_ids = []
            pair = transaction_pairs[symbol]
            for order_id, order in self.unfinished_orders.items():
                if symbol == order.symbol:
                    assert order.type in (OrderType.BUY_LIMIT, OrderType.SELL_LIMIT)
                    if order.type == OrderType.BUY_LIMIT and price <= order.price:
                        filled_cash_amount = order.amount * order.price
                        self.balance[pair.target] += order.amount * (1 - self.FEE)
                        self.balance[pair.base] -= filled_cash_amount
                        finished_order_ids.append(order_id)
                        self.orders[order_id].set_finished(order.amount, order.amount * self.FEE, filled_cash_amount)
                        self.notify_all_subscriptions(self.orders[order_id])
                    elif order.type == OrderType.SELL_LIMIT and price >= order.price:
                        filled_cash_amount = order.amount * order.price
                        self.balance[pair.target] -= order.amount
                        self.balance[pair.base] += filled_cash_amount * (1 - self.FEE)
                        finished_order_ids.append(order_id)
                        self.orders[order_id].set_finished(order.amount, filled_cash_amount * self.FEE, filled_cash_amount)
                        self.notify_all_subscriptions(self.orders[order_id])
            for order_id in finished_order_ids:
                del self.unfinished_orders[order_id]
