"""
Estratégias especializadas para criptomoedas de Large Cap (BTC, ETH).
Características: alta liquidez, menor volatilidade relativa, forte correlação com mercado.
"""

import os
import sys
from typing import Dict

import numpy as np
import pandas as pd

# Import correto da base strategy
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)
from base_strategy import BaseStrategy


class TrendFollowingEMAStrategy(BaseStrategy):
    """
    Estratégia Trend Following com EMA Crossover para Large Caps.

    Aproveita movimentos de médio e longo prazo com cruzamentos de EMAs.
    Ideal para BTC e ETH devido à estabilidade relativa.
    """

    def __init__(self, symbol: str, params: Dict = None):
        super().__init__(symbol, params)
        default_params = {
            "ema_fast": 50,  # EMA rápida
            "ema_slow": 200,  # EMA lenta
            "volume_multiplier": 1.3,  # Confirmação de volume
            "atr_period": 14,  # Período ATR para stop-loss
            "atr_multiplier": 2.0,  # Multiplicador ATR
        }
        if params:
            default_params.update(params)
        self.params = default_params

    def get_strategy_name(self) -> str:
        return "TrendFollowingEMA"

    def analyze(self, data: pd.DataFrame) -> Dict:
        """Análise baseada em cruzamento de EMAs com confirmação de volume."""
        if len(data) < max(self.params["ema_fast"], self.params["ema_slow"]):
            return self._insufficient_data_response(data)

        # Calcula EMAs
        ema_fast = data["close"].ewm(span=self.params["ema_fast"]).mean()
        ema_slow = data["close"].ewm(span=self.params["ema_slow"]).mean()

        # Calcula ATR para stop-loss dinâmico
        high_low = data["high"] - data["low"]
        high_close = np.abs(data["high"] - data["close"].shift())
        low_close = np.abs(data["low"] - data["close"].shift())
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = tr.rolling(window=self.params["atr_period"]).mean()

        # Volume médio
        volume_avg = data["volume"].rolling(window=20).mean()

        # Condições atuais
        current_price = data["close"].iloc[-1]
        current_ema_fast = ema_fast.iloc[-1]
        current_ema_slow = ema_slow.iloc[-1]
        prev_ema_fast = ema_fast.iloc[-2]
        prev_ema_slow = ema_slow.iloc[-2]
        current_volume = data["volume"].iloc[-1]
        avg_volume = volume_avg.iloc[-1]
        current_atr = atr.iloc[-1]

        # Detecta cruzamentos
        golden_cross = (current_ema_fast > current_ema_slow) and (prev_ema_fast <= prev_ema_slow)
        death_cross = (current_ema_fast < current_ema_slow) and (prev_ema_fast >= prev_ema_slow)

        # Confirmação de volume
        volume_confirmed = current_volume > (avg_volume * self.params["volume_multiplier"])

        # Força da tendência
        trend_strength = abs(current_ema_fast - current_ema_slow) / current_price
        strong_trend = trend_strength > 0.02  # 2% de diferença entre EMAs

        # Sinais de entrada/saída
        should_buy = golden_cross and volume_confirmed and strong_trend
        should_sell = death_cross or (
            current_ema_fast < current_ema_slow and trend_strength < 0.01
        )

        # Stop-loss dinâmico baseado em ATR
        stop_loss_distance = current_atr * self.params["atr_multiplier"]

        return {
            "should_buy": should_buy,
            "should_sell": should_sell,
            "confidence": min(trend_strength * 50, 1.0),
            "metadata": {
                "current_price": current_price,
                "indicators": {
                    "ema_fast": current_ema_fast,
                    "ema_slow": current_ema_slow,
                    "golden_cross": golden_cross,
                    "death_cross": death_cross,
                    "volume_confirmed": volume_confirmed,
                    "trend_strength": trend_strength,
                    "current_volume": current_volume,
                    "avg_volume": avg_volume,
                    "volume_ratio": current_volume / avg_volume if avg_volume > 0 else 0,
                    "atr": current_atr,
                    "stop_loss_distance": stop_loss_distance,
                    "dynamic_stop": current_price - stop_loss_distance,
                },
                "signals": {
                    "golden_cross": golden_cross,
                    "death_cross": death_cross,
                    "volume_confirmed": volume_confirmed,
                    "strong_trend": strong_trend,
                },
            },
        }


class MeanReversionRSIStrategy(BaseStrategy):
    """
    Estratégia Mean Reversion com RSI e divergências para Large Caps.

    Usa indicadores de sobrecompra/sobrevenda com análise de divergências.
    Ideal para BTC/ETH em movimentos laterais ou correções.
    """

    def __init__(self, symbol: str, params: Dict = None):
        super().__init__(symbol, params)
        default_params = {
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "bollinger_period": 20,
            "bollinger_std": 2.0,
            "volume_threshold": 1.2,
            "divergence_lookback": 5,  # Períodos para detectar divergências
        }
        if params:
            default_params.update(params)
        self.params = default_params

    def get_strategy_name(self) -> str:
        return "MeanReversionRSI"

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calcula o RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _detect_divergence(self, prices: pd.Series, rsi: pd.Series, lookback: int) -> Dict:
        """Detecta divergências entre preço e RSI."""
        if len(prices) < lookback + 1:
            return {"bullish": False, "bearish": False}

        recent_prices = prices.iloc[-lookback - 1 :]
        recent_rsi = rsi.iloc[-lookback - 1 :]

        # Divergência bullish: preço faz mínimos menores, RSI faz mínimos maiores
        price_lower_low = recent_prices.iloc[-1] < recent_prices.iloc[0]
        rsi_higher_low = recent_rsi.iloc[-1] > recent_rsi.iloc[0]
        bullish_div = price_lower_low and rsi_higher_low

        # Divergência bearish: preço faz máximos maiores, RSI faz máximos menores
        price_higher_high = recent_prices.iloc[-1] > recent_prices.iloc[0]
        rsi_lower_high = recent_rsi.iloc[-1] < recent_rsi.iloc[0]
        bearish_div = price_higher_high and rsi_lower_high

        return {"bullish": bullish_div, "bearish": bearish_div}

    def analyze(self, data: pd.DataFrame) -> Dict:
        """Análise baseada em RSI, Bollinger Bands e divergências."""
        if len(data) < max(self.params["rsi_period"], self.params["bollinger_period"]):
            return self._insufficient_data_response(data)

        # Calcula indicadores
        rsi = self._calculate_rsi(data["close"], self.params["rsi_period"])

        # Bollinger Bands
        bb_middle = data["close"].rolling(window=self.params["bollinger_period"]).mean()
        bb_std = data["close"].rolling(window=self.params["bollinger_period"]).std()
        bb_upper = bb_middle + (bb_std * self.params["bollinger_std"])
        bb_lower = bb_middle - (bb_std * self.params["bollinger_std"])

        # Volume
        volume_avg = data["volume"].rolling(window=20).mean()

        # Condições atuais
        current_price = data["close"].iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_volume = data["volume"].iloc[-1]
        avg_volume = volume_avg.iloc[-1]
        current_bb_upper = bb_upper.iloc[-1]
        current_bb_lower = bb_lower.iloc[-1]
        current_bb_middle = bb_middle.iloc[-1]

        # Detecta divergências
        divergence = self._detect_divergence(
            data["close"], rsi, self.params["divergence_lookback"]
        )

        # Posição nas Bollinger Bands
        bb_position = (current_price - current_bb_lower) / (current_bb_upper - current_bb_lower)

        # Confirmação de volume
        volume_confirmed = current_volume > (avg_volume * self.params["volume_threshold"])

        # Condições de entrada
        rsi_oversold = current_rsi < self.params["rsi_oversold"]
        rsi_overbought = current_rsi > self.params["rsi_overbought"]
        near_bb_lower = current_price < current_bb_lower * 1.02  # 2% acima da banda inferior
        near_bb_upper = current_price > current_bb_upper * 0.98  # 2% abaixo da banda superior

        # Sinais
        should_buy = (
            (rsi_oversold and near_bb_lower) or (divergence["bullish"] and current_rsi < 40)
        ) and volume_confirmed

        should_sell = (
            (rsi_overbought and near_bb_upper) or (divergence["bearish"] and current_rsi > 60)
        ) and volume_confirmed

        # Confidence baseado na força dos sinais
        confidence = 0.5
        if rsi_oversold and near_bb_lower:
            confidence += 0.3
        if divergence["bullish"] or divergence["bearish"]:
            confidence += 0.2

        return {
            "should_buy": should_buy,
            "should_sell": should_sell,
            "confidence": min(confidence, 1.0),
            "metadata": {
                "current_price": current_price,
                "indicators": {
                    "rsi": current_rsi,
                    "rsi_oversold_level": self.params["rsi_oversold"],
                    "rsi_overbought_level": self.params["rsi_overbought"],
                    "bb_upper": current_bb_upper,
                    "bb_lower": current_bb_lower,
                    "bb_middle": current_bb_middle,
                    "bb_position": bb_position,
                    "current_volume": current_volume,
                    "avg_volume": avg_volume,
                    "volume_ratio": current_volume / avg_volume if avg_volume > 0 else 0,
                    "bullish_divergence": divergence["bullish"],
                    "bearish_divergence": divergence["bearish"],
                },
                "signals": {
                    "rsi_oversold": rsi_oversold,
                    "rsi_overbought": rsi_overbought,
                    "near_bb_lower": near_bb_lower,
                    "near_bb_upper": near_bb_upper,
                    "volume_confirmed": volume_confirmed,
                    "bullish_divergence": divergence["bullish"],
                    "bearish_divergence": divergence["bearish"],
                },
            },
        }


class SwingTradingStrategy(BaseStrategy):
    """
    Estratégia Swing Trading em Suportes/Resistências para Large Caps.

    Identifica zonas de acúmulo/distribuição em timeframes maiores.
    Entrada próximo a suporte, saída perto da resistência.
    """

    def __init__(self, symbol: str, params: Dict = None):
        super().__init__(symbol, params)
        default_params = {
            "pivot_period": 20,  # Período para calcular pivôs
            "support_resistance_strength": 3,  # Mínimo de toques para validar S/R
            "proximity_threshold": 0.015,  # 1.5% de proximidade para S/R
            "volume_confirmation": 1.5,  # Multiplicador de volume
            "fibonacci_levels": [0.236, 0.382, 0.618, 0.786],  # Níveis de Fibonacci
        }
        if params:
            default_params.update(params)
        self.params = default_params

    def get_strategy_name(self) -> str:
        return "SwingTrading"

    def _find_pivot_points(self, data: pd.DataFrame, period: int) -> Dict:
        """Encontra pontos de pivô (suportes e resistências)."""
        highs = data["high"].rolling(window=period * 2 + 1, center=True).max()
        lows = data["low"].rolling(window=period * 2 + 1, center=True).min()

        # Identifica pivôs
        pivot_highs = data["high"] == highs
        pivot_lows = data["low"] == lows

        # Extrai níveis significativos
        resistance_levels = data.loc[pivot_highs, "high"].dropna().tail(10).tolist()
        support_levels = data.loc[pivot_lows, "low"].dropna().tail(10).tolist()

        return {
            "resistance": sorted(set(resistance_levels), reverse=True),
            "support": sorted(set(support_levels)),
        }

    def _calculate_fibonacci_levels(self, high: float, low: float) -> Dict:
        """Calcula níveis de retração de Fibonacci."""
        diff = high - low
        return {level: high - (diff * level) for level in self.params["fibonacci_levels"]}

    def _find_nearest_support_resistance(self, price: float, levels: Dict) -> Dict:
        """Encontra o suporte e resistência mais próximos."""
        supports = [level for level in levels["support"] if level < price]
        resistances = [level for level in levels["resistance"] if level > price]

        nearest_support = max(supports) if supports else None
        nearest_resistance = min(resistances) if resistances else None

        return {"support": nearest_support, "resistance": nearest_resistance}

    def analyze(self, data: pd.DataFrame) -> Dict:
        """Análise baseada em suportes, resistências e Fibonacci."""
        if len(data) < self.params["pivot_period"] * 3:
            return self._insufficient_data_response(data)

        current_price = data["close"].iloc[-1]
        current_volume = data["volume"].iloc[-1]
        volume_avg = data["volume"].rolling(window=20).mean().iloc[-1]

        # Encontra pivôs
        levels = self._find_pivot_points(data, self.params["pivot_period"])
        nearest = self._find_nearest_support_resistance(current_price, levels)

        # Calcula Fibonacci para o último swing
        recent_high = data["high"].tail(self.params["pivot_period"]).max()
        recent_low = data["low"].tail(self.params["pivot_period"]).min()
        fib_levels = self._calculate_fibonacci_levels(recent_high, recent_low)

        # Verifica proximidade com níveis importantes
        near_support = False
        near_resistance = False

        if nearest["support"]:
            support_distance = abs(current_price - nearest["support"]) / current_price
            near_support = support_distance < self.params["proximity_threshold"]

        if nearest["resistance"]:
            resistance_distance = abs(current_price - nearest["resistance"]) / current_price
            near_resistance = resistance_distance < self.params["proximity_threshold"]

        # Verifica proximidade com Fibonacci
        near_fib_support = any(
            abs(current_price - level) / current_price < self.params["proximity_threshold"]
            for level in fib_levels.values()
            if level < current_price
        )

        near_fib_resistance = any(
            abs(current_price - level) / current_price < self.params["proximity_threshold"]
            for level in fib_levels.values()
            if level > current_price
        )

        # Confirmação de volume
        volume_confirmed = current_volume > (volume_avg * self.params["volume_confirmation"])

        # Momentum de curto prazo
        sma_short = data["close"].rolling(window=5).mean().iloc[-1]
        momentum_bullish = current_price > sma_short

        # Sinais
        should_buy = (near_support or near_fib_support) and momentum_bullish and volume_confirmed
        should_sell = (near_resistance or near_fib_resistance) and not momentum_bullish

        # Confidence baseado na qualidade dos níveis
        confidence = 0.5
        if near_support and volume_confirmed:
            confidence += 0.3
        if near_fib_support:
            confidence += 0.2

        return {
            "should_buy": should_buy,
            "should_sell": should_sell,
            "confidence": min(confidence, 1.0),
            "metadata": {
                "current_price": current_price,
                "nearest_support": nearest["support"],
                "nearest_resistance": nearest["resistance"],
                "near_support": near_support,
                "near_resistance": near_resistance,
                "fibonacci_levels": fib_levels,
                "near_fib_support": near_fib_support,
                "near_fib_resistance": near_fib_resistance,
                "volume_confirmed": volume_confirmed,
                "momentum_bullish": momentum_bullish,
            },
        }
