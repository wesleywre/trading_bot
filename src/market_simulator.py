"""
Gerador de dados simulados para teste do bot de trading.
"""

import random
import time
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd


class SimulatedMarketData:
    """Gera dados de mercado simulados para teste."""

    def __init__(self):
        self.base_prices = {
            "BTC/USDT": 45000.0,
            "ETH/USDT": 3000.0,
            "BNB/USDT": 300.0,
            "ADA/USDT": 0.5,
            "SOL/USDT": 100.0,
            "XRP/USDT": 0.6,
        }

        self.current_prices = self.base_prices.copy()
        self.trends = {symbol: 0.0 for symbol in self.base_prices}

    def generate_price_movement(self, symbol: str) -> float:
        """Gera movimento de preço simulado."""
        # Volatilidade baseada no tipo de ativo
        if "BTC" in symbol or "ETH" in symbol:
            volatility = 0.02  # 2% máximo
        else:
            volatility = 0.05  # 5% máximo

        # Adiciona alguma tendência
        trend = self.trends.get(symbol, 0.0)

        # Movimento aleatório com tendência
        movement = random.uniform(-volatility, volatility) + trend * 0.1

        # Atualiza preço
        self.current_prices[symbol] *= 1 + movement

        # Atualiza tendência ocasionalmente
        if random.random() < 0.1:  # 10% chance de mudar tendência
            self.trends[symbol] = random.uniform(-0.02, 0.02)

        return self.current_prices[symbol]

    def generate_ohlcv_data(self, symbol: str, periods: int = 100) -> List[List]:
        """Gera dados OHLCV simulados."""
        data = []
        current_time = datetime.now()

        for i in range(periods):
            timestamp = current_time - timedelta(hours=periods - i)

            # Preço base para este período
            base_price = self.generate_price_movement(symbol)

            # Gera OHLCV
            open_price = base_price * random.uniform(0.99, 1.01)
            close_price = base_price * random.uniform(0.99, 1.01)
            high_price = max(open_price, close_price) * random.uniform(1.0, 1.02)
            low_price = min(open_price, close_price) * random.uniform(0.98, 1.0)
            volume = random.uniform(1000, 10000)

            data.append(
                [
                    int(timestamp.timestamp() * 1000),  # timestamp
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                ]
            )

        return data

    def get_current_price(self, symbol: str) -> float:
        """Retorna preço atual simulado."""
        return self.generate_price_movement(symbol)

    def get_24h_stats(self, symbol: str) -> Dict:
        """Retorna estatísticas simuladas de 24h."""
        current_price = self.current_prices[symbol]
        yesterday_price = current_price * random.uniform(0.95, 1.05)

        change = (current_price - yesterday_price) / yesterday_price

        return {
            "symbol": symbol,
            "price": current_price,
            "change": change,
            "changePercent": change * 100,
            "volume": random.uniform(100000, 1000000),
            "high": current_price * random.uniform(1.0, 1.05),
            "low": current_price * random.uniform(0.95, 1.0),
        }


# Instância global para manter estado
_market_simulator = SimulatedMarketData()


def get_simulated_ohlcv(symbol: str, timeframe: str = "1h", limit: int = 100):
    """Interface compatível com ccxt."""
    return _market_simulator.generate_ohlcv_data(symbol, limit)


def get_simulated_ticker(symbol: str):
    """Interface compatível com ccxt para ticker."""
    stats = _market_simulator.get_24h_stats(symbol)
    return {
        "symbol": symbol,
        "last": stats["price"],
        "percentage": stats["changePercent"],
        "change": stats["change"],
        "baseVolume": stats["volume"],
        "high": stats["high"],
        "low": stats["low"],
    }
