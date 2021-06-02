import abc
from datetime import datetime

from constants import *
from strategy import BaseStrategy


class SinglePairStrategy(BaseStrategy, abc.ABC):
    def __init__(self, trader, symbol, enable_logger, root_dir):
        self.start_time = datetime.now()
        super().__init__(enable_logger=enable_logger, root_dir=root_dir,
                         topic=f'Grid_strategy_{self.start_time.strftime("%Y%m%d_%H%M%S")}')
        self.trader = trader
        self.symbol = symbol
        self.pair = transaction_pairs[symbol]
