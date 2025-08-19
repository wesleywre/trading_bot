from typing import Dict

import pandas as pd

from .base_strategy import BaseStrategy


class SimpleMomentumStrategy(BaseStrategy):
    """Estratégia baseada em momentum simples."""

    def get_strategy_name(self) -> str:
        return "SimpleMomentum"

    def analyze(self, data: pd.DataFrame) -> Dict:
        """
        Analisa os dados usando a estratégia de momentum.

        Args:
            data: DataFrame com dados OHLCV

        Returns:
            Dict com sinais de trading e metadados
        """
        current_price = data["close"].iloc[-1]
        previous_price = data["close"].iloc[-2] if len(data) > 1 else current_price
        last_change = (
            (current_price - previous_price) / previous_price if previous_price > 0 else 0.0
        )

        drop_threshold = self.parameters.get("DROP_THRESHOLD", 0.01)
        rise_threshold = self.parameters.get("RISE_THRESHOLD", 0.005)
        max_hold_hours = self.parameters.get("MAX_HOLD_HOURS", 5)

        should_buy = last_change < -drop_threshold
        should_sell = last_change > rise_threshold

        return {
            "should_buy": should_buy,
            "should_sell": should_sell,
            "metadata": {
                "current_price": current_price,
                "last_change": last_change,
                "drop_threshold": drop_threshold,
                "rise_threshold": rise_threshold,
                "max_hold_hours": max_hold_hours,
            },
        }
