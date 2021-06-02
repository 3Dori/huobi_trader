import abc
from datetime import datetime

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

    @property
    def base_symbol(self):
        return self.pair.base

    @property
    def target_symbol(self):
        return self.pair.target
