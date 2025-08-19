from typing import Dict

import pandas as pd

from .base_strategy import BaseStrategy


class TrailingStopStrategy(BaseStrategy):
    """Estratégia com Trailing Stop Dinâmico."""

    def __init__(self, symbol: str, parameters: dict):
        super().__init__(symbol, parameters)
        self.highest_price = 0
        self.stop_loss_price = 0

    def get_strategy_name(self) -> str:
        return "TrailingStop"

    def analyze(self, data: pd.DataFrame) -> Dict:
        """
        Analisa os dados usando trailing stop dinâmico.
        """
        current_price = data["close"].iloc[-1]
        previous_price = data["close"].iloc[-2] if len(data) > 1 else current_price
        last_change = (
            (current_price - previous_price) / previous_price if previous_price > 0 else 0.0
        )

        drop_threshold = self.parameters.get("DROP_THRESHOLD", 0.01)
        trailing_pct = self.parameters.get("TRAILING_PCT", 0.02)  # 2% trailing stop

        # Atualiza o preço máximo se necessário
        if current_price > self.highest_price:
            self.highest_price = current_price
            # Atualiza o stop loss baseado no novo máximo
            self.stop_loss_price = self.highest_price * (1 - trailing_pct)

        should_buy = last_change < -drop_threshold

        # Vende se o preço cair abaixo do trailing stop
        should_sell = current_price <= self.stop_loss_price if self.stop_loss_price > 0 else False

        return {
            "should_buy": should_buy,
            "should_sell": should_sell,
            "metadata": {
                "current_price": current_price,
                "last_change": last_change,
                "highest_price": self.highest_price,
                "stop_loss_price": self.stop_loss_price,
                "trailing_pct": trailing_pct,
                "drop_threshold": drop_threshold,
            },
        }
