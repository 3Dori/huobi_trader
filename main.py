import json
import os
from pathlib import Path

from constants import *
from trader.trader import Trader
from strategy import *

from huobi.constant import *

trader = None


def main():
    api_config = Path(os.path.join('.', 'API_key.json'))
    with api_config.open('rt') as handle:
        config = json.load(handle)
    global trader
    trader = Trader(config['api_key'], config['secret_key'], config['account_id'])


main()
