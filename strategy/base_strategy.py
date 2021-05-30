import abc

from logger import Logger


class BaseStrategy(object):
    def __init__(self, enable_logger=True, root_dir=None):
        self.logger = Logger(root_dir, 'Grid strategy') if enable_logger else None
        self.enable_logger = enable_logger
        self._stopped = False

    @abc.abstractmethod
    def feed(self, price):
        pass

    @abc.abstractmethod
    def start(self, price):
        pass

    @abc.abstractmethod
    def run(self):
        pass

    @abc.abstractmethod
    def stop(self):
        self._stopped = True
