import abc

from logger import Logger


class BaseStrategy(abc.ABC):
    def __init__(self, enable_logger=True, root_dir=None, topic=None):
        self.logger = Logger(root_dir, topic) if enable_logger else None
        self.enable_logger = enable_logger

    @abc.abstractmethod
    def feed(self, price):
        pass

    @abc.abstractmethod
    def start(self, price):
        pass
