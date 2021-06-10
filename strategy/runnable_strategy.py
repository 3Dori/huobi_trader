import abc
import threading
import time
import warnings

from strategy import BaseStrategy


class RunnableStrategy(BaseStrategy, abc.ABC):
    def __init__(self, interval):
        if interval is not None and interval < 0:
            raise ValueError('interval must be greater than 0')
        self.interval = interval
        self.thread = None
        self._started = False
        self._stopped = False
        self.exit = threading.Event()

    @abc.abstractmethod
    def start_impl(self, price):
        pass

    def start(self, price=None):
        if price is None:
            price = self.trader.get_newest_price(self.symbol)
        if self._started:
            warnings.warn('Strategy already started')
            return
        if self.interval is not None:
            self.start_impl(price)
            self.thread = threading.Thread(target=self.run, args=())
            self.thread.start()
        else:
            self.start_impl(price)
        self._started = True

    def run(self):
        while True:
            self.exit.wait(self.interval)
            if self._stopped:
                break
            try:
                newest_price = self.trader.get_newest_price(self.symbol)
                self.feed(newest_price)
            except RuntimeError:
                if self.enable_logger:
                    self.logger.error('Unable to read the newest price from the trader')
        if self.enable_logger:
            self.logger.info('Strategy successfully stopped')

    def stop(self):
        if self._started:
            self._stopped = True
            self.exit.set()

    def __del__(self):
        self.stop()
