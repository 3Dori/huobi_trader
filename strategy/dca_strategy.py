from .base_strategy import BaseStrategy


class DCAStrategy(BaseStrategy):
    def __init__(self, symbol, dca_type, target_profit,
                 base_order_size, safety_order_size,
                 max_safety_orders=3, max_active_safety_orders=1,
                 safety_order_deviation=1, safety_order_volumn_scale=1,
                 safety_order_step_scale=1):
        super().__init__()

    def feed(self, price):
        pass

    def start(self, price):
        pass

    def run(self):
        pass

    def stop(self):
        pass
