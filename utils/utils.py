from huobi.constant import *


def get_seconds_of_candlestick_interval(candlestick_interval):
    if candlestick_interval == CandlestickInterval.MIN1:
        return 60
    elif candlestick_interval == CandlestickInterval.MIN5:
        return 300
    elif candlestick_interval == CandlestickInterval.MIN15:
        return 900
    elif candlestick_interval == CandlestickInterval.MIN30:
        return 1800
    elif candlestick_interval == CandlestickInterval.MIN60:
        return 3600
    elif candlestick_interval == CandlestickInterval.HOUR4:
        return 14400
    elif candlestick_interval == CandlestickInterval.DAY1:
        return 86400
    else:
        raise NotImplementedError()
