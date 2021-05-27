import threading
import time


class StopLoss(object):
    def __init__(self, symbol, trader, stop_loss_price, interval=10, trailing_order=None):
        self.symbol = symbol
        self.trader = trader
        self.stop_loss_price = stop_loss_price
        self.interval = interval
        if trailing_order is not None and not isinstance(trailing_order, dict):
            raise TypeError('trailing_order must be a dictionary')
        self.trailing_order = trailing_order

        self._stopped = False
        self.thread = threading.Thread(target=self.run, args=())
        self.thread.start()

    def __repr__(self):
        return f'<{self.symbol}: {self.stop_loss_price}>'

    def stop(self):
        self._stopped = True

    def run(self):
        print(f'Stop loss started: {self}.')
        while True:
            if self._stopped:
                print('Stop loss thread canceled manually')
                self.trader.stop_loss_threads.remove(self)
                break
            newest_price = self.trader.get_newest_price(self.symbol)
            if newest_price < self.stop_loss_price:
                try:
                    self.trader.cancel_all_sell_orders(self.symbol)
                    order = self.trader.sell_all_at_market_price(self.symbol)
                    print(f'Stop loss triggered at price: {newest_price}')
                    self.trader.stop_loss_threads.remove(self)
                    if self.trailing_order is not None:
                        amount = float(order.amount)
                        self.trader.create_buy_queue(symbol=self.symbol, total_amount=amount, **self.trailing_order)
                        print('Created trailing order')
                    break
                except Exception as e:
                    print(e)
            time.sleep(self.interval)