from constants import *
from .base_trader import BaseTrader

from huobi.constant import *
from huobi.utils import *
from huobi.client.algo import AlgoClient
from huobi.client.trade import TradeClient
from huobi.client.account import AccountClient
from huobi.client.market import MarketClient

import numpy as np
import scipy.stats as stats

import time


class Trader(BaseTrader):
    def __init__(self, api_key, secret_key, account_id):
        super().__init__()
        self.account_id = account_id
        self.trade_client = TradeClient(api_key=api_key, secret_key=secret_key)
        self.account_client = AccountClient(api_key=api_key, secret_key=secret_key)
        self.algo_client = AlgoClient(api_key=api_key, secret_key=secret_key)
        self.market_client = MarketClient()
        self.holds = {}
        self.total_fee = 0
        self.stop_loss_threads = []
        self.long_order_threads = []
        self.latest_timestamp = 0
        self.client_id_counter = 0

    def get_balance(self, symbol='usdt'):
        balances = self.account_client.get_balance(self.account_id)
        for balance in balances:
            if balance.currency == symbol:
                return float(balance.balance)

    def get_balance_pair(self, symbol):
        pair = transaction_pairs[symbol]
        target, base = pair.target, pair.base
        balances = self.account_client.get_balance(self.account_id)
        target_balance, base_balance = None, None
        for balance in balances:
            if balance.currency == target and target_balance is None:
                target_balance = float(balance.balance)
            elif balance.currency == base and base_balance is None:
                base_balance = float(balance.balance)
        return target_balance, base_balance

    def get_newest_price(self, symbol):
        newest_trade = self.market_client.get_market_trade(symbol=symbol)[0]
        return newest_trade.price

    def generate_orders(self, symbol, prices, amounts, order_type):
        client_order_id_header = str(int(time.time()))
        order_ids = [f'{client_order_id_header}{symbol}{i:02d}' for i in range(len(prices))]
        pair = transaction_pairs[symbol]
        price_scale, amount_scale = pair.price_scale, pair.amount_scale
        orders = [
            {
                'account_id': self.account_id,
                'symbol': symbol,
                'order_type': order_type,
                'source': OrderSource.API,
                'amount': f'{self.correct_amount(amount, symbol):.{amount_scale}f}',
                'price': f'{price:.{price_scale}f}',
                'client_order_id': order_id
            }
            for amount, price, order_id in zip(amounts, prices, order_ids)
        ]
        return orders

    @staticmethod
    def get_normalized_amounts_with_eagerness(num_orders, eagerness=1.0):
        amounts = np.geomspace(eagerness**num_orders, 1, num_orders)
        return amounts / np.sum(amounts)

    @staticmethod
    def get_normalized_amounts_with_normal_distr(num_orders, skewness=1.0):
        amounts = np.linspace(- skewness, skewness, num_orders)
        amounts = stats.norm.pdf(amounts, 0, 1)
        amounts += amounts.min()
        return amounts / np.sum(amounts)

    @staticmethod
    def get_normalized_amounts_with_distr(num_orders, distr):
        if distr is None:
            return Trader.get_normalized_amounts_with_eagerness(num_orders, 1.0)
        elif distr['distr'] == 'geometry':
            return Trader.get_normalized_amounts_with_eagerness(num_orders, distr.get('eagerness', 1.0))
        elif distr['distr'] == 'normal':
            return Trader.get_normalized_amounts_with_normal_distr(num_orders, distr.get('skewness', 1.0))

    @staticmethod
    def get_price_interval(lower_price, upper_price, num_orders, order_type):
        if order_type == OrderType.BUY_LIMIT:
            prices = np.linspace(upper_price, lower_price, num_orders)
        elif order_type == OrderType.SELL_LIMIT:
            prices = np.linspace(lower_price, upper_price, num_orders)
        else:
            raise ValueError(f'Unknown order type {order_type}')
        return prices

    def submit_orders(self, orders):
        results = []
        for i in range(0, len(orders), MAX_ORDER_NUM):
            create_results = self.trade_client.batch_create_order(order_config_list=orders[i:i+MAX_ORDER_NUM])
            results += create_results
        return results

    def generate_buy_queue_orders(self, symbol, lower_price, upper_price, num_orders,
                                  total_amount=None, total_amount_fraction=None, distr=None):
        prices = self.get_price_interval(lower_price, upper_price, num_orders, OrderType.BUY_LIMIT)
        normalized_amounts = self.get_normalized_amounts_with_distr(num_orders, distr)
        if total_amount is not None:
            amounts = normalized_amounts * total_amount
        elif total_amount_fraction is not None:
            balance = self.get_balance(transaction_pairs[symbol].base) * total_amount_fraction
            amounts = normalized_amounts * (balance / prices * normalized_amounts).sum()
        else:
            raise ValueError('One of total_amount or total_amount_fraction should be given')
        orders = self.generate_orders(symbol, prices, amounts, OrderType.BUY_LIMIT)
        return orders

    def create_smart_buy_queue(self, symbol, lower_price, upper_price, num_orders, profit=1.05,
                               total_amount=None, total_amount_fraction=None, distr=None):
        orders = self.generate_buy_queue_orders(symbol, lower_price, upper_price, num_orders, total_amount,
                                                total_amount_fraction, distr)
        results = self.submit_orders(orders)
        LogInfo.output_list(results)
        client_order_id_header = str(int(time.time()))
        price_scale = transaction_pairs[symbol].price_scale
        algo_order_ids = []
        for i, order in enumerate(orders):
            client_order_id = f'{client_order_id_header}{symbol}{i:02d}'
            order_price = float(order['price']) * profit
            stop_price = order_price * 0.999
            self.algo_client.create_order(
                account_id=self.account_id, symbol=symbol, order_side=OrderSide.SELL, order_type=AlgoOrderType.LIMIT,
                order_size=order['amount'], order_price=f'{order_price:.{price_scale}f}',
                stop_price=f'{stop_price:.{price_scale}f}',
                client_order_id=client_order_id)
            algo_order_ids.append(client_order_id)
        return results, orders, algo_order_ids

    def cancel_all_algo_orders(self, order_ids):
        results = [self.algo_client.cancel_orders(order_id) for order_id in order_ids]
        return results

    def update_timestamp(self):
        now = int(time.time())
        if now == self.latest_timestamp:
            self.client_id_counter += 1
        else:
            self.latest_timestamp = now
            self.client_id_counter = 0

    def get_order(self, order_id):
        return self.trade_client.get_order(order_id)

    def create_order(self, symbol, price, order_type, amount=None, amount_fraction=None):
        pair = transaction_pairs[symbol]
        if amount is None:
            if order_type is OrderType.SELL_LIMIT or order_type is OrderType.SELL_MARKET:
                amount = self.get_balance(pair.target) * amount_fraction
            else:
                amount = self.get_balance(pair.base) * amount_fraction
        amount = f'{float(amount):.{pair.amount_scale}f}'
        if price is not None:
            price = f'{float(price):.{pair.price_scale}f}'
        self.update_timestamp()
        client_order_id = f'{self.latest_timestamp}{symbol}{self.client_id_counter:02d}'
        order_id = self.trade_client.create_order(
            symbol=symbol, account_id=self.account_id, order_type=order_type, price=price,
            amount=amount, source=OrderSource.API, client_order_id=client_order_id)
        return order_id

    @staticmethod
    def get_time():
        return int(time.time())

    def get_previous_prices(self, symbol, window_type, window_size):
        candlesticks = self.market_client.get_candlestick(symbol, window_type, window_size)
        return [(cs.id, (cs.open + cs.close)/2) for cs in sorted(candlesticks, key=lambda cs: cs.id)]

    def create_buy_queue(self, symbol, lower_price, upper_price, num_orders,
                         total_amount=None, total_amount_fraction=None, distr=None):
        newest_price = self.get_newest_price(symbol)
        if lower_price > newest_price:
            raise ValueError('Unable to buy at a price higher the the market price')
        if lower_price >= upper_price:
            raise ValueError('lower_price should be less than upper_price')
        orders = self.generate_buy_queue_orders(symbol, lower_price, upper_price, num_orders,
                                                total_amount, total_amount_fraction, distr)
        results = self.submit_orders(orders)
        LogInfo.output_list(results)
        return results, orders

    def create_sell_queue(self, symbol, lower_price, upper_price, num_orders,
                          total_amount=None, total_amount_fraction=None, distr=None):
        newest_price = self.get_newest_price(symbol)
        if upper_price < newest_price:
            raise ValueError('Unable to sell at a price lower the the market price')
        if lower_price >= upper_price:
            raise ValueError('lower_price should be less than upper_price')
        prices = self.get_price_interval(lower_price, upper_price, num_orders, OrderType.SELL_LIMIT)
        normalized_amounts = self.get_normalized_amounts_with_distr(num_orders, distr)
        if total_amount is not None:
            amounts = normalized_amounts * total_amount
        elif total_amount_fraction is not None:
            balance = self.get_balance(transaction_pairs[symbol].target) * total_amount_fraction
            amounts = normalized_amounts * balance
        else:
            raise ValueError('One of total_amount or total_amount_fraction should be given')
        orders = self.generate_orders(symbol, prices, amounts, OrderType.SELL_LIMIT)
        results = self.submit_orders(orders)
        LogInfo.output_list(results)
        return results, orders

    def cancel_orders(self, symbol, order_ids):
        cancel_results = []
        for i in range(0, len(order_ids), MAX_CANCEL_ORDER_NUM):
            cancel_result = self.trade_client.cancel_orders(symbol, order_ids[i:i+MAX_CANCEL_ORDER_NUM])
            cancel_results.append(cancel_result)
        return cancel_results

    def cancel_all_orders_with_type(self, symbol, order_type):
        account_spot = self.account_client.get_account_by_type_and_symbol(AccountType.SPOT, symbol=None)
        orders = self.trade_client.get_open_orders(symbol=symbol, account_id=account_spot.id, direct=QueryDirection.NEXT)
        sell_order_ids = [str(order.id) for order in orders if order.type == order_type]
        if len(sell_order_ids) == 0:
            return
        return self.cancel_orders(symbol, sell_order_ids)

    def cancel_all_buy_orders(self, symbol):
        return self.cancel_all_orders_with_type(symbol, OrderType.BUY_LIMIT)

    def cancel_all_sell_orders(self, symbol):
        return self.cancel_all_orders_with_type(symbol, OrderType.SELL_LIMIT)

    def sell_all_at_market_price(self, symbol):
        return self.create_order(symbol=symbol, price=None, order_type=OrderType.SELL_MARKET, amount_fraction=0.999)

    def start_new_stop_loss_thread(self, symbol, stop_loss_price, interval=10, trailing_order=None):
        from stop_loss import StopLoss
        thread = StopLoss(symbol, self, stop_loss_price, interval, trailing_order)
        self.stop_loss_threads.append(thread)

    def start_long_order_thread(self, symbol, buy_price, profit, amount=None, amount_fraction=None,
                                stop_loss=0.9, interval=10):
        from long_order import LongOrder
        thread = LongOrder(symbol, self, buy_price, profit, amount, amount_fraction, stop_loss, interval)
        self.long_order_threads.append(thread)