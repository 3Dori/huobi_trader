import abc


class BaseStrategy(object):
    def __init__(self):
        pass

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
        pass
