"""
Estratégias especializadas para criptomoedas de Mid Cap (BNB, ADA, SOL, XRP).
Características: volatilidade moderada, bons volumes mas menos previsíveis.
"""

import os
import sys
from typing import Dict

import pandas as pd

# Import correto da base strategy
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)
from base_strategy import BaseStrategy


class BreakoutTradingStrategy(BaseStrategy):
    """
    Estratégia de Breakout para Mid Caps:
    - Detecta rompimentos de resistência/suporte
    - Volume confirmação obrigatória
    - Stop loss dinâmico
    """

    def __init__(self, symbol: str, params: Dict = None):
        super().__init__(symbol, params)
        # Parâmetros padrão para estratégia de breakout
        default_params = {
            "consolidation_period": 20,
            "min_consolidation_period": 10,
            "max_consolidation_range": 0.03,
            "breakout_threshold": 0.005,
            "volume_multiplier": 1.8,
            "stop_loss_distance": 0.02,
        }
        self.params = {**default_params, **(params or {})}

    def get_strategy_name(self) -> str:
        return "BreakoutTrading"

    def _detect_consolidation(self, data: pd.DataFrame) -> Dict:
        """Detecta padrões de consolidação."""
        period = self.params["consolidation_period"]
        if len(data) < period:
            return {"in_consolidation": False, "range_high": None, "range_low": None}

        recent_data = data.tail(period)
        range_high = recent_data["high"].max()
        range_low = recent_data["low"].min()
        range_size = (range_high - range_low) / recent_data["close"].mean()

        # Verifica se está em consolidação
        in_consolidation = range_size < self.params["max_consolidation_range"]

        # Verifica se o preço está se mantendo no range
        price_in_range_count = 0
        for _, row in recent_data.iterrows():
            if range_low <= row["close"] <= range_high:
                price_in_range_count += 1

        consolidation_strength = price_in_range_count / len(recent_data)
        valid_consolidation = (
            in_consolidation
            and consolidation_strength > 0.8
            and len(recent_data) >= self.params["min_consolidation_period"]
        )

        return {
            "in_consolidation": valid_consolidation,
            "range_high": range_high,
            "range_low": range_low,
            "range_size": range_size,
            "consolidation_strength": consolidation_strength,
        }

    def analyze(self, data: pd.DataFrame) -> Dict:
        """Análise baseada em breakouts de consolidação."""
        if len(data) < self.params["consolidation_period"]:
            return self._insufficient_data_response(data)

        current_price = data["close"].iloc[-1]
        current_volume = data["volume"].iloc[-1]
        volume_avg = data["volume"].rolling(window=20).mean().iloc[-1]

        # Detecta consolidação
        consolidation = self._detect_consolidation(data)

        if not consolidation["in_consolidation"]:
            return {
                "should_buy": False,
                "should_sell": False,
                "confidence": 0.0,
                "metadata": {
                    "current_price": current_price,
                    "consolidation_detected": False,
                    "reason": "Não há consolidação válida",
                },
            }

        range_high = consolidation["range_high"]
        range_low = consolidation["range_low"]
        range_middle = (range_high + range_low) / 2

        # Calcula distâncias
        distance_to_high = (range_high - current_price) / current_price
        distance_to_low = (current_price - range_low) / current_price

        # Detecta breakouts
        upward_breakout = current_price > range_high * (1 + self.params["breakout_threshold"])
        downward_breakout = current_price < range_low * (1 - self.params["breakout_threshold"])

        # Confirmação de volume
        volume_confirmed = current_volume > (volume_avg * self.params["volume_multiplier"])

        # Momentum de curto prazo
        sma_5 = data["close"].rolling(window=5).mean().iloc[-1]
        momentum_bullish = current_price > sma_5

        # Sinais
        should_buy = upward_breakout and volume_confirmed and momentum_bullish
        should_sell = downward_breakout and volume_confirmed and not momentum_bullish

        # Confidence baseado na qualidade do breakout
        confidence = 0.5
        if volume_confirmed:
            confidence += 0.3
        if consolidation["consolidation_strength"] > 0.9:
            confidence += 0.2

        # Stop loss levels
        stop_loss_buy = range_high * (1 - self.params["stop_loss_distance"])
        stop_loss_sell = range_low * (1 + self.params["stop_loss_distance"])

        return {
            "should_buy": should_buy,
            "should_sell": should_sell,
            "confidence": min(confidence, 1.0),
            "metadata": {
                "current_price": current_price,
                "range_high": range_high,
                "range_low": range_low,
                "range_middle": range_middle,
                "upward_breakout": upward_breakout,
                "downward_breakout": downward_breakout,
                "volume_confirmed": volume_confirmed,
                "consolidation_strength": consolidation["consolidation_strength"],
                "stop_loss_buy": stop_loss_buy,
                "stop_loss_sell": stop_loss_sell,
            },
        }


class MomentumVolumeStrategy(BaseStrategy):
    """
    Estratégia de Momentum com Volume para Mid Caps:
    - Combina momentum de preço com volume
    - Detecta movimentos sustentados
    - Entrada em impulsos de volume
    """

    def __init__(self, symbol: str, params: Dict = None):
        super().__init__(symbol, params)
        self.params = params if params else {}

    def get_strategy_name(self) -> str:
        return "MomentumVolume"

    def _calculate_macd(self, prices: pd.Series) -> Dict:
        """Calcula MACD."""
        ema_fast = prices.ewm(span=self.params["macd_fast"]).mean()
        ema_slow = prices.ewm(span=self.params["macd_slow"]).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.params["macd_signal"]).mean()
        histogram = macd_line - signal_line

        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calcula RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def analyze(self, data: pd.DataFrame) -> Dict:
        """Análise baseada em momentum de preço e volume."""
        if len(data) < max(self.params["macd_slow"], self.params["volume_period"]):
            return self._insufficient_data_response(data)

        current_price = data["close"].iloc[-1]
        current_volume = data["volume"].iloc[-1]

        # Calcula indicadores
        momentum_period = self.params["momentum_period"]
        price_momentum = (current_price - data["close"].iloc[-momentum_period]) / data[
            "close"
        ].iloc[-momentum_period]

        volume_avg = data["volume"].rolling(window=self.params["volume_period"]).mean()
        current_volume_avg = volume_avg.iloc[-1]
        volume_ratio = current_volume / current_volume_avg

        macd_data = self._calculate_macd(data["close"])
        current_macd = macd_data["macd"].iloc[-1]
        current_signal = macd_data["signal"].iloc[-1]
        current_histogram = macd_data["histogram"].iloc[-1]
        prev_histogram = macd_data["histogram"].iloc[-2]

        rsi = self._calculate_rsi(data["close"])
        current_rsi = rsi.iloc[-1]

        # Detecta cruzamentos MACD
        macd_bullish_cross = current_macd > current_signal and current_histogram > prev_histogram
        macd_bearish_cross = current_macd < current_signal and current_histogram < prev_histogram

        # Condições de momentum
        strong_price_momentum = abs(price_momentum) > self.params["price_momentum_threshold"]
        bullish_momentum = price_momentum > 0
        volume_confirmed = volume_ratio >= self.params["volume_multiplier"]
        rsi_momentum = current_rsi > self.params["rsi_momentum_threshold"]

        # Força do movimento
        momentum_strength = abs(price_momentum) / self.params["price_momentum_threshold"]
        volume_strength = min(volume_ratio / self.params["volume_multiplier"], 3.0)  # Cap em 3x

        # Sinais
        should_buy = (
            strong_price_momentum
            and bullish_momentum
            and volume_confirmed
            and macd_bullish_cross
            and rsi_momentum
        )

        should_sell = (
            strong_price_momentum
            and not bullish_momentum
            and volume_confirmed
            and macd_bearish_cross
            and current_rsi < 40
        )

        # Confidence baseado na força dos sinais
        confidence = 0.3
        if volume_confirmed:
            confidence += 0.2 * min(volume_strength / 2, 1)
        if strong_price_momentum:
            confidence += 0.2 * min(momentum_strength, 1)
        if macd_bullish_cross or macd_bearish_cross:
            confidence += 0.3

        return {
            "should_buy": should_buy,
            "should_sell": should_sell,
            "confidence": min(confidence, 1.0),
            "metadata": {
                "current_price": current_price,
                "price_momentum": price_momentum,
                "volume_ratio": volume_ratio,
                "macd": current_macd,
                "macd_signal": current_signal,
                "macd_histogram": current_histogram,
                "rsi": current_rsi,
                "macd_bullish_cross": macd_bullish_cross,
                "macd_bearish_cross": macd_bearish_cross,
                "momentum_strength": momentum_strength,
                "volume_strength": volume_strength,
            },
        }


class LiquidityScalpingStrategy(BaseStrategy):
    """
    Estratégia de Scalping com análise de liquidez para Mid Caps:
    - Aproveitamento de spreads
    - Entradas rápidas em zonas de liquidez
    - Exits automáticos
    """

    def __init__(self, symbol: str, params: Dict = None):
        super().__init__(symbol, params)
        self.params = params if params else {}

    def _detect_micro_trend(self, data: pd.DataFrame) -> Dict:
        """Detecta micro-tendências de curto prazo."""
        period = self.params["scalp_timeframe"]
        if len(data) < period:
            return {"trend": "neutral", "strength": 0}

        recent_data = data.tail(period)

        # Análise de micro-momentum
        price_changes = recent_data["close"].pct_change().dropna()
        volume_changes = recent_data["volume"].pct_change().dropna()

        avg_price_change = price_changes.mean()
        price_volatility = price_changes.std()
        volume_momentum = volume_changes.mean()

        # Determina tendência
        if avg_price_change > self.params["price_change_threshold"]:
            trend = "bullish"
        elif avg_price_change < -self.params["price_change_threshold"]:
            trend = "bearish"
        else:
            trend = "neutral"

        # Força da tendência
        strength = min(abs(avg_price_change) / self.params["price_change_threshold"], 2.0)

        return {
            "trend": trend,
            "strength": strength,
            "price_momentum": avg_price_change,
            "volume_momentum": volume_momentum,
            "volatility": price_volatility,
        }

    def _calculate_vwap(self, data: pd.DataFrame, period: int = 10) -> pd.Series:
        """Calcula VWAP (Volume Weighted Average Price)."""
        typical_price = (data["high"] + data["low"] + data["close"]) / 3
        vwap = (typical_price * data["volume"]).rolling(window=period).sum() / data[
            "volume"
        ].rolling(window=period).sum()
        return vwap

    def analyze(self, data: pd.DataFrame) -> Dict:
        """Análise para scalping baseada em micro-movimentos."""
        if len(data) < self.params["scalp_timeframe"] + 5:
            return self._insufficient_data_response(data)

        current_price = data["close"].iloc[-1]
        current_volume = data["volume"].iloc[-1]

        # Detecta micro-tendência
        micro_trend = self._detect_micro_trend(data)

        # VWAP
        vwap = self._calculate_vwap(data)
        current_vwap = vwap.iloc[-1]
        price_vs_vwap = (current_price - current_vwap) / current_vwap

        # Volume analysis
        volume_avg = data["volume"].rolling(window=self.params["scalp_timeframe"]).mean().iloc[-1]
        volume_spike = current_volume > (volume_avg * self.params["volume_spike_multiplier"])

        # Momentum ultra-curto
        momentum_period = self.params["momentum_period"]
        short_momentum = (current_price - data["close"].iloc[-momentum_period]) / data[
            "close"
        ].iloc[-momentum_period]

        # Verifica condições de liquidez (simulado - em produção seria order book real)
        # Para simulação, usa volatilidade como proxy
        recent_volatility = data["close"].tail(10).pct_change().std()
        good_liquidity = recent_volatility < 0.02  # Baixa volatilidade = boa liquidez

        # Sinais de entrada
        bullish_scalp = (
            micro_trend["trend"] == "bullish"
            and micro_trend["strength"] > 1.0
            and price_vs_vwap > 0.001  # Acima do VWAP
            and volume_spike
            and good_liquidity
            and short_momentum > 0
        )

        bearish_scalp = (
            micro_trend["trend"] == "bearish"
            and micro_trend["strength"] > 1.0
            and price_vs_vwap < -0.001  # Abaixo do VWAP
            and volume_spike
            and good_liquidity
            and short_momentum < 0
        )

        # Sinais de saída (rápidos para scalping)
        should_sell = (
            micro_trend["trend"] != "bullish" or not volume_spike or price_vs_vwap < -0.002
        )

        # Confidence para scalping (mais conservador)
        confidence = 0.4
        if volume_spike:
            confidence += 0.2
        if micro_trend["strength"] > 1.5:
            confidence += 0.2
        if good_liquidity:
            confidence += 0.2

        return {
            "should_buy": bullish_scalp,
            "should_sell": should_sell or bearish_scalp,
            "confidence": min(confidence, 1.0),
            "metadata": {
                "current_price": current_price,
                "micro_trend": micro_trend["trend"],
                "trend_strength": micro_trend["strength"],
                "vwap": current_vwap,
                "price_vs_vwap": price_vs_vwap,
                "volume_spike": volume_spike,
                "volume_ratio": current_volume / volume_avg if volume_avg > 0 else 1,
                "short_momentum": short_momentum,
                "good_liquidity": good_liquidity,
                "profit_target": self.params["profit_target"],
                "stop_loss": self.params["stop_loss"],
            },
        }
