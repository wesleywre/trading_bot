from abc import ABC, abstractmethod
from typing import Dict

import pandas as pd


class BaseStrategy(ABC):
    """Classe base para todas as estratégias de trading."""

    def __init__(self, symbol: str, parameters: Dict = None):
        self.symbol = symbol
        self.parameters = parameters or {}

    @abstractmethod
    def analyze(self, data: pd.DataFrame) -> Dict:
        """
        Analisa os dados do mercado e retorna um dicionário com sinais de trading.

        Returns:
            dict: {
                'should_buy': bool,
                'should_sell': bool,
                'confidence': float,  # 0.0 a 1.0
                'metadata': dict  # Informações adicionais específicas da estratégia
            }
        """
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Retorna o nome da estratégia."""
        pass

    def _insufficient_data_response(self, data: pd.DataFrame) -> Dict:
        """Resposta padrão quando não há dados suficientes."""
        current_price = data["close"].iloc[-1] if len(data) > 0 else 0.0
        return {
            "should_buy": False,
            "should_sell": False,
            "confidence": 0.0,
            "metadata": {
                "current_price": current_price,
                "insufficient_data": True,
                "data_length": len(data),
            },
        }
