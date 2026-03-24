from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List, Optional, Tuple
import json
import numpy as np


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


class Helper:
    def __init__(self):
        self.MAX_TOMATOES_HISTORY = 80

    def update_trader_state(self, trader_state: dict, market: MarketView) -> dict:
        if market.product == "TOMATOES":
            if market.mid_price is not None:
                if (
                    len(trader_state["tomatoes_mid_prices"])
                    >= self.MAX_TOMATOES_HISTORY
                ):
                    trader_state["tomatoes_mid_prices"].pop(0)
                trader_state["tomatoes_mid_prices"].append(market.mid_price)

            if market.best_bid is not None and market.best_ask is not None:
                if (
                    len(trader_state["tomatoes_spread_history"])
                    >= self.MAX_TOMATOES_HISTORY
                ):
                    trader_state["tomatoes_spread_history"].pop(0)
                trader_state["tomatoes_spread_history"].append(
                    market.best_ask - market.best_bid
                )

        return trader_state

    def check_regime(
        self, z_score: float, trend_score: float, z_threshold=1.5, trend_threshold=0.3
    ) -> str:
        if abs(z_score) < z_threshold:
            return "neutral"
        elif abs(trend_score) < trend_threshold:
            return "mean_reversion"
        elif abs(trend_score) >= trend_threshold:
            if np.sign(z_score) == np.sign(trend_score):
                return "momentum"
            else:
                return "mean_reversion"
        return "neutral"


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
        helper: Helper,
    ) -> List[Order]:
        return []


class MR_MomentumStrategy(BaseStrategy):

    def generate_orders(
        self,
        product: str,
        market: MarketView,
        position: int,
        position_limit: int,
        state: TradingState,
        trader_state: dict,
        helper: Helper,
    ) -> List[Order]:
        om = OrderManager(product, position, position_limit)

        mid_prices = trader_state.get("tomatoes_mid_prices", [])
        spread_history = trader_state.get("tomatoes_spread_history", [])
        current_mid_price = market.mid_price
        current_spread = spread_history[-1] if spread_history else None

        if len(mid_prices) < 30 or len(spread_history) < 30:
            return []

        rolling_mid_price_mean = np.mean(mid_prices[-20:])
        rolling_std = np.std(mid_prices[-30:])
        z_score = (
            (current_mid_price - rolling_mid_price_mean) / rolling_std
            if rolling_std > 0
            else 0
        )
        trend_score = (
            ((np.mean(mid_prices[-10:]) - np.mean(mid_prices[-30:-10])) / rolling_std)
            if rolling_std > 0
            else 0
        )

        regime = helper.check_regime(z_score, trend_score)
        if market.best_bid is not None and market.best_ask is not None:
            if regime == "mean_reversion":
                if z_score > 0:
                    om.sell(market.best_bid, market.best_bid_volume)
                elif z_score < 0:
                    om.buy(market.best_ask, market.best_ask_volume)
            elif regime == "momentum":
                if trend_score > 0:
                    om.buy(market.best_ask, market.best_ask_volume)
                elif trend_score < 0:
                    om.sell(market.best_bid, market.best_bid_volume)

        return om.get_orders()


class Trader:
    POSITION_LIMITS = {
        "EMERALDS": 20,
        "TOMATOES": 20,
    }

    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {
            # "EMERALDS": ExampleFairValueStrategy({"EMERALDS": 10000}),
            # "TOMATOES": ExampleFairValueStrategy({"TOMATOES": 5000}),
            "TOMATOES": MR_MomentumStrategy(),
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
        helper = Helper()

        # Initialize trader state if empty
        if isinstance(trader_state, dict) and not trader_state:
            trader_state = {
                "tomatoes_mid_prices": [],
                "tomatoes_spread_history": [],
            }

        for product, order_depth in state.order_depths.items():
            position = state.position.get(product, 0)
            position_limit = self.POSITION_LIMITS.get(product, 0)
            market = MarketView(product, order_depth)

            # Updating trader_state, history will include current timestep
            trader_state = helper.update_trader_state(trader_state, market)

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
                helper=helper,
            )
            result[product] = orders

        conversions = 0
        next_trader_data = self.dump_trader_state(trader_state)
        return result, conversions, next_trader_data
