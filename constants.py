class TransactionPair(object):
    def __init__(self, price_scale, amount_scale, target, base):
        self.price_scale = price_scale
        self.amount_scale = amount_scale
        self.target = target
        self.base = base


transaction_pairs = {
    'ethusdt': TransactionPair(2, 4, 'eth', 'usdt'),
    'btcusdt': TransactionPair(2, 6, 'btc', 'usdt'),
    'eth3susdt': TransactionPair(8, 4, 'eth3s', 'usdt'),
    'btc3susdt': TransactionPair(6, 4, 'btc3s', 'usdt'),
    'shibusdt': TransactionPair(8, 2, 'shib', 'usdt'),
    'dogeusdt': TransactionPair(6, 2, 'doge', 'usdt'),
    'eosusdt': TransactionPair(4, 4, 'eos', 'usdt'),
    'eos3susdt': TransactionPair(4, 4, 'eos3s', 'usdt'),
    'linkusdt': TransactionPair(4, 2, 'link', 'usdt'),
    'link3susdt': TransactionPair(8, 4, 'link3s', 'usdt'),
    'ethbtc': TransactionPair(6, 4, 'eth', 'btc')
}


MAX_ORDER_NUM = 10
MAX_CANCEL_ORDER_NUM = 50