from typing import Dict

import pandas as pd

from .base_strategy import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    """Estratégia Mean Reversion usando Bollinger Bands e RSI."""

    def get_strategy_name(self) -> str:
        return "MeanReversion"

    def analyze(self, data: pd.DataFrame) -> Dict:
        """
        Analisa usando Bollinger Bands e RSI para mean reversion.
        """
        if len(data) < 20:  # Precisa de pelo menos 20 períodos
            return self._default_response(data)

        current_price = data["close"].iloc[-1]

        # Parâmetros configuráveis
        bb_period = self.parameters.get("BB_PERIOD", 20)
        bb_std = self.parameters.get("BB_STD", 2)
        rsi_period = self.parameters.get("RSI_PERIOD", 14)
        rsi_oversold = self.parameters.get("RSI_OVERSOLD", 30)
        rsi_overbought = self.parameters.get("RSI_OVERBOUGHT", 70)

        # Calcula Bollinger Bands manualmente
        sma = data["close"].rolling(window=bb_period).mean()
        std = data["close"].rolling(window=bb_period).std()
        bb_upper = sma + (std * bb_std)
        bb_lower = sma - (std * bb_std)
        bb_middle = sma

        # Calcula RSI manualmente
        delta = data["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # Valores atuais
        current_bb_upper = bb_upper.iloc[-1]
        current_bb_lower = bb_lower.iloc[-1]
        current_bb_middle = bb_middle.iloc[-1]
        current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50

        # Condições para compra (oversold)
        touching_lower_band = current_price <= current_bb_lower * 1.01  # 1% de tolerância
        rsi_oversold_condition = current_rsi < rsi_oversold

        # Condições para venda (overbought)
        touching_upper_band = current_price >= current_bb_upper * 0.99  # 1% de tolerância
        rsi_overbought_condition = current_rsi > rsi_overbought

        # Condições para saída (retorno à média)
        price_near_middle = (
            abs(current_price - current_bb_middle) / current_bb_middle < 0.005
        )  # 0.5%

        # Sinais
        should_buy = touching_lower_band and rsi_oversold_condition
        should_sell = (touching_upper_band and rsi_overbought_condition) or price_near_middle

        return {
            "should_buy": should_buy,
            "should_sell": should_sell,
            "metadata": {
                "current_price": current_price,
                "last_change": (
                    (current_price - data["close"].iloc[-2]) / data["close"].iloc[-2]
                    if len(data) > 1 and data["close"].iloc[-2] > 0
                    else 0.0
                ),
                "bb_upper": current_bb_upper,
                "bb_middle": current_bb_middle,
                "bb_lower": current_bb_lower,
                "rsi": current_rsi,
                "touching_lower_band": touching_lower_band,
                "touching_upper_band": touching_upper_band,
                "rsi_oversold": rsi_oversold_condition,
                "rsi_overbought": rsi_overbought_condition,
                "price_near_middle": price_near_middle,
                "bb_width": ((current_bb_upper - current_bb_lower) / current_bb_middle * 100),
            },
        }

    def _default_response(self, data: pd.DataFrame) -> Dict:
        """Resposta padrão quando não há dados suficientes."""
        current_price = data["close"].iloc[-1]
        return {
            "should_buy": False,
            "should_sell": False,
            "metadata": {
                "current_price": current_price,
                "last_change": (
                    (current_price - data["close"].iloc[-2]) / data["close"].iloc[-2]
                    if len(data) > 1 and data["close"].iloc[-2] > 0
                    else 0.0
                ),
                "insufficient_data": True,
            },
        }
