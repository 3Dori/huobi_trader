import abc
from datetime import datetime

from huobi.constant import *

from constants import *
from strategy import BaseStrategy


class SinglePairStrategy(BaseStrategy, abc.ABC):
    def __init__(self, trader, symbol, target_asset, base_asset, enable_logger, root_dir):
        self.start_time = datetime.now()
        BaseStrategy.__init__(self, enable_logger=enable_logger, root_dir=root_dir,
                              topic=f'{self.__class__.__name__}_{self.start_time.strftime("%Y%m%d_%H%M%S")}')
        self.trader = trader
        self.symbol = symbol
        self.pair = transaction_pairs[symbol]

        target_balance, base_balance = self.trader.get_balance_pair(symbol)
        if target_balance < target_asset:
            raise RuntimeError(f'Insufficient balance for {self.target_symbol}')
        if base_balance < base_asset:
            raise RuntimeError(f'Insufficient balance for {self.base_symbol}')
        self.target_asset = target_asset
        self.base_asset = base_asset
        self.initial_target_asset = target_asset
        self.initial_base_asset = base_asset
        self.initial_total_asset_in_base = 0
        self.initial_price = 0
        self.newest_price = 0

    def get_total_asset(self, in_base=False):
        """Return current available assets of the target and base currency of the symbol."""
        total_asset_in_base = self.base_asset + self.target_asset * self.newest_price
        total_asset_in_target = total_asset_in_base / self.newest_price
        if in_base:
            return total_asset_in_base
        else:
            return total_asset_in_base, total_asset_in_target

    def cancel_orders(self, order_ids):
        try:
            self.trader.cancel_orders(self.symbol, order_ids)
        except RuntimeError as e:
            if self.enable_logger:
                self.logger.error(f'Unable to cancel order: {e.args}')

    def create_order(self, price, order_type, amount=None):
        try:
            order_id = self.trader.create_order(self.symbol, price, order_type, amount)
            # if order_type == OrderType.BUY_MARKET:
            #     order = self.trader.get_order(order_id)
            #     self.base_asset -= float(order.filled_cash_amount)
            #     self.target_asset += float(order.filled_amount) - float(order.filled_fees)
            # elif order_type == OrderType.SELL_MARKET:
            #     order = self.trader.get_order(order_id)
            #     self.base_asset += float(order.filled_cash_amount) - float(order.filled_fees)
            #     self.target_asset -= float(order.filled_amount)
            if order_type in (OrderType.BUY_MARKET, OrderType.SELL_MARKET):
                price = self.newest_price
            if self.enable_logger:
                self.logger.info(f'Created order. Type: {order_type}; '
                                 f'price: {price:.{self.pair.price_scale}f}; '
                                 f'amount: {amount:.{self.pair.amount_scale}f}')
            return order_id
        except Exception as e:
            if self.enable_logger:
                self.logger.error(f'Unable to create order. Type: {order_type}; '
                                  f'price: {price:.{self.pair.price_scale}f}; '
                                  f'amount: {amount:.{self.pair.amount_scale}f}; error: {e.args}')
            else:
                raise e

    @property
    def base_symbol(self):
        return self.pair.base

    @property
    def target_symbol(self):
        return self.pair.target
