from huobi.constant import *

import threading
import time


class LongOrder(object):
    def __init__(self, symbol, trader, buy_price, profit, amount=None, amount_fraction=None, stop_loss=0.9, interval=10):
        self.symbol = symbol
        self.trader = trader
        self.buy_price = buy_price
        if profit < 1.004:
            raise ValueError('profit should be greater than 1.004')
        self.profit = profit
        self.stop_loss = 0.9
        self.interval = interval

        self.order_id = self.trader.create_order(symbol, buy_price, OrderType.BUY_LIMIT, amount=amount, amount_fraction=amount_fraction).id
        self._stopped = False
        self.thread = threading.Thread(target=self.run, args=())
        self.thread.start()

    def __repr__(self):
        return f'<{self.symbol}: {self.buy_price} * {self.profit}>'

    def stop(self):
        self._stopped = True
    
    def run(self):
        print(f'Long order started: {self}.')
        while True:
            if self._stopped:
                print('Long order thread canceled manually')
                self.trader.long_order_threads.remove(self)
                break
            order = self.trader.get_order(self.order_id)
            if order.canceled_at != 0:
                print(f'{self} Order canceled')
                self.trader.long_order_threads.remove(self)
                break
            if order.finished_at != 0:
                newest_price = self.trader.get_newest_price(self.symbol)
                if newest_price >= self.buy_price * self.profit:
                    try:
                        amount = float(order.amount) * 0.99
                        self.trader.create_order(self.symbol, None, OrderType.SELL_MARKET, amount=amount)
                        print(f'Long order ended at price: {newest_price}')
                        self.trader.stop_loss_threads.remove(self)
                        break
                    except Exception as e:
                        print(e)
                elif newest_price < self.buy_price * self.stop_loss:
                    try:
                        amount = float(order.amount) * 0.99
                        self.trader.create_order(self.symbol, None, OrderType.SELL_MARKET, amount=amount)
                        print(f'Long order stopped at price: {newest_price}')
                        self.trader.stop_loss_threads.remove(self)
                        break
                    except Exception as e:
                        print(e)
            time.sleep(self.interval)