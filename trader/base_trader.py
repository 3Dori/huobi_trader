import abc

from constants import *


class BaseTrader(object):
    FEE = 0.002

    def __init__(self):
        pass

    @abc.abstractmethod
    def add_trade_clearing_subscription(self, symbol, callback, error_handler=None):
        pass

    @abc.abstractmethod
    def remove_trade_clearing_subscription(self, subscription):
        pass

    @abc.abstractmethod
    def get_balance(self, symbol='usdt'):
        pass

    @abc.abstractmethod
    def get_balance_pair(self, symbol):
        pass

    @abc.abstractmethod
    def get_newest_price(self, symbol):
        pass

    @abc.abstractmethod
    def get_order(self, order_id):
        pass

    @abc.abstractmethod
    def create_order(self, symbol, price, order_type, amount=None, amount_fraction=None):
        pass

    @abc.abstractmethod
    def submit_orders(self, symbol, prices, amounts, order_type):
        pass

    @abc.abstractmethod
    def cancel_orders(self, symbol, order_ids):
        pass

    @staticmethod
    def correct_amount(amount, symbol):
        # Reduce the amount by one smallest decimal precision to avoid insufficient balance caused by round-up errors
        scale = transaction_pairs[symbol].amount_scale
        return amount - 10 ** -scale
