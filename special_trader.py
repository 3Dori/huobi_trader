import threading
import time


class ETH1STrader20210520(object):
    def __init__(self, trader, interval=10):
        self.trader = trader
        self.interval = interval

        self._stopped = False
        self.thread = threading.Thread(target=self.run, args=())
        self.thread.start()

    def stop(self):
        self._stopped = True

    def run(self):
        print(f'ETH1STrader started')
        while True:
            if self._stopped:
                print('ETH1STrader canceled manually')
                self.trader.stop_loss_threads.remove(self)
                break
            newest_price = self.trader.get_newest_price(self.symbol)
            if newest_price < self.stop_loss_price:
                try:
                    self.trader.cancel_all_sell_orders(self.symbol)
                    self.trader.sell_all_at_market_price(self.symbol)
                    print(f'Stop loss triggered at price: {newest_price}')
                    self.trader.stop_loss_threads.remove(self)
                    break
                except Exception as e:
                    print(e)
            time.sleep(self.interval)