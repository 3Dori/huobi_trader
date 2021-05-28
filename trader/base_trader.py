import abc


class BaseTrader(object):
    FEE = 0.002

    def __init__(self):
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
    def cancel_orders(self, symbol, order_ids):
        pass

