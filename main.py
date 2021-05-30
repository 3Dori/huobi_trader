from constants import *
from trader.trader import Trader

from huobi.constant import *

def main():
    # trader = Trader(API_KEY, SECRET_KEY, ACCOUNT_ID)
    # trader.create_sell_queue('btcusdt', lower_price=45350, upper_price=45577, total_amount=0.001)
    pass


trader = Trader(API_KEY, SECRET_KEY, ACCOUNT_ID)

if __name__ == '__main__':
    main()
