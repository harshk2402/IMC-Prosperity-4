from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List, Optional, Tuple
import json


class MarketView:
    def __init__(self, product: str, order_depth: OrderDepth):
        self.product = product
        self.order_depth = order_depth

        self.buy_orders = order_depth.buy_orders
        self.sell_orders = order_depth.sell_orders

        self.best_bid = max(self.buy_orders.keys()) if self.buy_orders else None
        self.best_ask = min(self.sell_orders.keys()) if self.sell_orders else None

        self.best_bid_volume = (
            self.buy_orders[self.best_bid] if self.best_bid is not None else 0
        )
        self.best_ask_volume = (
            -self.sell_orders[self.best_ask] if self.best_ask is not None else 0
        )

    @property
    def mid_price(self) -> Optional[float]:
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return None


class OrderManager:
    def __init__(self, product: str, position: int, position_limit: int):
        self.product = product
        self.position = position
        self.position_limit = position_limit
        self.orders: List[Order] = []

        self.pending_buy = 0
        self.pending_sell = 0

    def remaining_buy_capacity(self) -> int:
        return self.position_limit - (self.position + self.pending_buy)

    def remaining_sell_capacity(self) -> int:
        return self.position_limit + (self.position - self.pending_sell)

    def buy(self, price: int, quantity: int) -> None:
        qty = min(quantity, self.remaining_buy_capacity())
        if qty > 0:
            self.orders.append(Order(self.product, price, qty))
            self.pending_buy += qty

    def sell(self, price: int, quantity: int) -> None:
        qty = min(quantity, self.remaining_sell_capacity())
        if qty > 0:
            self.orders.append(Order(self.product, price, -qty))
            self.pending_sell += qty

    def get_orders(self) -> List[Order]:
        return self.orders


class BaseStrategy:
    def generate_orders(
        self,
        product: str,
        market: MarketView,
        position: int,
        position_limit: int,
        state: TradingState,
        trader_state: dict,
    ) -> List[Order]:
        return []


class ExampleFairValueStrategy(BaseStrategy):
    def __init__(self, fair_values: Dict[str, int]):
        self.fair_values = fair_values

    def generate_orders(
        self,
        product: str,
        market: MarketView,
        position: int,
        position_limit: int,
        state: TradingState,
        trader_state: dict,
    ) -> List[Order]:
        om = OrderManager(product, position, position_limit)
        fair_value = self.fair_values.get(product)

        if fair_value is None:
            return []

        if market.best_ask is not None and market.best_ask < fair_value:
            om.buy(market.best_ask, market.best_ask_volume)

        if market.best_bid is not None and market.best_bid > fair_value:
            om.sell(market.best_bid, market.best_bid_volume)

        return om.get_orders()


class Trader:
    POSITION_LIMITS = {
        "AMETHYSTS": 20,
        "STARFRUIT": 20,
    }

    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {
            "AMETHYSTS": ExampleFairValueStrategy({"AMETHYSTS": 10000}),
            "STARFRUIT": ExampleFairValueStrategy({"STARFRUIT": 5000}),
        }

    def load_trader_state(self, raw: str) -> dict:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def dump_trader_state(self, state: dict) -> str:
        return json.dumps(state)

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        trader_state = self.load_trader_state(state.traderData)

        for product, order_depth in state.order_depths.items():
            position = state.position.get(product, 0)
            position_limit = self.POSITION_LIMITS.get(product, 0)
            market = MarketView(product, order_depth)

            strategy = self.strategies.get(product)
            if strategy is None:
                result[product] = []
                continue

            orders = strategy.generate_orders(
                product=product,
                market=market,
                position=position,
                position_limit=position_limit,
                state=state,
                trader_state=trader_state,
            )
            result[product] = orders

        conversions = 0
        next_trader_data = self.dump_trader_state(trader_state)
        return result, conversions, next_trader_data
