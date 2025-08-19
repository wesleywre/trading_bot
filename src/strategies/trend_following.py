from typing import Dict

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    """Estratégia Trend Following com SMA, Volume e indicadores simples."""

    def get_strategy_name(self) -> str:
        return "TrendFollowing"

    def analyze(self, data: pd.DataFrame) -> Dict:
        """
        Analisa tendência usando SMA 50/200 e volume.
        """
        if len(data) < 200:  # Precisa de pelo menos 200 períodos para SMA 200
            return self._default_response(data)

        current_price = data["close"].iloc[-1]

        # Calcula SMAs manualmente
        sma_50 = data["close"].rolling(window=50).mean()
        sma_200 = data["close"].rolling(window=200).mean()

        # Calcula ADX simplificado (usando ATR e DI)
        high = data["high"]
        low = data["low"]
        close = data["close"]

        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()

        # Movimento direcional simplificado
        dm_plus = np.where(
            (high - high.shift(1)) > (low.shift(1) - low), np.maximum(high - high.shift(1), 0), 0
        )
        dm_minus = np.where(
            (low.shift(1) - low) > (high - high.shift(1)), np.maximum(low.shift(1) - low, 0), 0
        )

        dm_plus_smooth = pd.Series(dm_plus).rolling(window=14).mean()
        dm_minus_smooth = pd.Series(dm_minus).rolling(window=14).mean()

        # DI+ e DI-
        di_plus = 100 * dm_plus_smooth / atr
        di_minus = 100 * dm_minus_smooth / atr

        # ADX simplificado
        dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus)
        adx = dx.rolling(window=14).mean()

        # Calcula volume médio
        volume_avg = data["volume"].rolling(window=20).mean()

        # Condições atuais
        current_sma50 = sma_50.iloc[-1]
        current_sma200 = sma_200.iloc[-1]
        prev_sma50 = sma_50.iloc[-2] if len(sma_50) > 1 else current_sma50
        prev_sma200 = sma_200.iloc[-2] if len(sma_200) > 1 else current_sma200
        current_adx = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0
        current_volume = data["volume"].iloc[-1]
        avg_volume = volume_avg.iloc[-1] if not pd.isna(volume_avg.iloc[-1]) else current_volume

        # Detecta cruzamento de SMAs
        golden_cross = (current_sma50 > current_sma200) and (prev_sma50 <= prev_sma200)
        death_cross = (current_sma50 < current_sma200) and (prev_sma50 >= prev_sma200)

        # Confirmações
        strong_trend = current_adx > 25
        high_volume = current_volume > avg_volume * 1.2  # Volume 20% acima da média

        # Sinais de compra e venda
        should_buy = golden_cross and strong_trend and high_volume
        should_sell = death_cross or (current_adx < 20)  # Tendência enfraquecendo

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
                "sma_50": current_sma50,
                "sma_200": current_sma200,
                "adx": current_adx,
                "volume_ratio": current_volume / avg_volume if avg_volume > 0 else 1,
                "golden_cross": golden_cross,
                "death_cross": death_cross,
                "strong_trend": strong_trend,
                "high_volume": high_volume,
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
