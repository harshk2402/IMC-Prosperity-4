from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List, Optional, Tuple, Any
import json
import numpy as np


class MarketView:
    def __init__(self, product: str, order_depth: OrderDepth):
        self.product = product
        self.order_depth = order_depth

        self.buy_orders = order_depth.buy_orders
        self.sell_orders = order_depth.sell_orders

        self.bid_levels = sorted(
            [(price, volume) for price, volume in self.buy_orders.items()], reverse=True
        )
        self.ask_levels = sorted(
            [(price, volume) for price, volume in self.sell_orders.items()]
        )

        self.best_bid = max(self.buy_orders.keys()) if self.buy_orders else None
        self.best_ask = min(self.sell_orders.keys()) if self.sell_orders else None

        self.best_bid_volume = (
            self.buy_orders[self.best_bid] if self.best_bid is not None else 0
        )
        self.best_ask_volume = (
            -self.sell_orders[self.best_ask] if self.best_ask is not None else 0
        )

        self.total_bid_volume = sum(self.buy_orders.values())
        self.total_ask_volume = -sum(self.sell_orders.values())
        self.bid_ask_imbalance = (
            (
                (self.total_bid_volume - self.total_ask_volume)
                / (self.total_bid_volume + self.total_ask_volume)
            )
            if self.total_bid_volume + self.total_ask_volume > 0
            else 0
        )
        self.top_of_book_imbalance = (
            (
                (self.best_bid_volume - self.best_ask_volume)
                / (self.best_bid_volume + self.best_ask_volume)
            )
            if self.best_bid_volume + self.best_ask_volume > 0
            else 0
        )

        self.spread = (
            self.best_ask - self.best_bid
            if self.best_bid is not None and self.best_ask is not None
            else None
        )

        self.vwap_bid_top_n = self.calculate_vwap(self.bid_levels, n=5)
        self.vwap_ask_top_n = self.calculate_vwap(
            self.ask_levels, n=5
        )  # 5 is arbitrary, can be tuned

    @property
    def mid_price(self) -> Optional[float]:
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return None

    def calculate_vwap(self, levels: List[Tuple[int, int]], n: int) -> Optional[float]:
        if not levels:
            return None
        top_levels = levels[:n]
        total_volume = sum(abs(volume) for price, volume in top_levels)
        if total_volume == 0:
            return None
        vwap = sum(price * abs(volume) for price, volume in top_levels) / total_volume
        return vwap


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

    def manage_position(
        self,
        signal: float,
        current_position: int,
        position_limit: int,
        aggression: float,
        market: MarketView,
        expected_movement: float,
    ) -> List[Order]:
        target_position = int(signal * aggression)
        target_position = max(
            min(target_position, position_limit), -position_limit
        )  # ensure target is within limits
        position_diff = target_position - current_position
        om = OrderManager(market.product, current_position, position_limit)
        spread = (
            market.best_ask - market.best_bid
            if market.best_bid is not None and market.best_ask is not None
            else 0
        )
        cost = spread / 2
        cost_const = 1.5

        if expected_movement > cost_const * cost:
            if position_diff > 0 and market.best_ask is not None:
                om.buy(market.best_ask, min(position_diff, market.best_ask_volume))
            elif position_diff < 0 and market.best_bid is not None:
                om.sell(market.best_bid, min(-position_diff, market.best_bid_volume))

        return om.get_orders()


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
    def generate_signal(
        self,
        product: str,
        market: MarketView,
        position: int,
        position_limit: int,
        state: TradingState,
        trader_state: dict,
        helper: Helper,
    ) -> Tuple[float, float, float]:
        return (0, 0, 0)


class MR_MomentumStrategy(BaseStrategy):

    def generate_signal(
        self,
        product: str,
        market: MarketView,
        position: int,
        position_limit: int,
        state: TradingState,
        trader_state: dict,
        helper: Helper,
    ) -> Tuple[float, float, float]:
        MR_AGGRESSION = 3
        MOM_AGGRESSION = 8
        mid_prices = trader_state.get("tomatoes_mid_prices", [])
        spread_history = trader_state.get("tomatoes_spread_history", [])

        if market.mid_price is None:
            return (0, 0, 0)

        current_mid_price = market.mid_price

        if len(mid_prices) < 30 or len(spread_history) < 30:
            return (0, 0, 0)

        rolling_mid_price_mean = np.mean(mid_prices[-20:])
        rolling_std = np.std(mid_prices[-30:])
        z_score = (
            ((current_mid_price - rolling_mid_price_mean) / rolling_std)
            if rolling_std > 0
            else 0
        )
        trend_score = (
            ((np.mean(mid_prices[-10:]) - np.mean(mid_prices[-30:-10])) / rolling_std)
            if rolling_std > 0
            else 0
        )

        regime = helper.check_regime(z_score, trend_score)

        if regime == "mean_reversion":
            expected_movement = abs(z_score) * rolling_std
            return (-z_score, MR_AGGRESSION, float(expected_movement))
        elif regime == "momentum":
            expected_movement = abs(trend_score) * rolling_std
            return (0, 0, 0)
            return (trend_score, MOM_AGGRESSION, float(expected_movement))

        return (0, 0, 0)


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
        if "tomatoes_mid_prices" not in trader_state:
            trader_state["tomatoes_mid_prices"] = []
        if "tomatoes_spread_history" not in trader_state:
            trader_state["tomatoes_spread_history"] = []

        for product, order_depth in state.order_depths.items():
            result[product] = []
            position = state.position.get(product, 0)
            position_limit = self.POSITION_LIMITS.get(product, 0)
            market = MarketView(product, order_depth)

            # Updating trader_state, history will include current timestep
            trader_state = helper.update_trader_state(trader_state, market)

            strategy = self.strategies.get(product)
            if strategy is None:
                signal = 0
                continue

            signal, aggression, expected_movement = strategy.generate_signal(
                product=product,
                market=market,
                position=position,
                position_limit=position_limit,
                state=state,
                trader_state=trader_state,
                helper=helper,
            )

            result[product] = helper.manage_position(
                signal,
                position,
                position_limit,
                aggression,
                market=market,
                expected_movement=expected_movement,
            )

        conversions = 0
        next_trader_data = self.dump_trader_state(trader_state)
        return result, conversions, next_trader_data
