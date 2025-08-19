"""
Factory para criação de estratégias de trading baseadas no tipo de ativo.
"""

from enum import Enum
from typing import Dict, Type

from .base_strategy import BaseStrategy
from .large_cap import (
    MeanReversionRSIStrategy,
    SwingTradingStrategy,
    TrendFollowingEMAStrategy,
)
from .mid_cap import (
    BreakoutTradingStrategy,
    LiquidityScalpingStrategy,
    MomentumVolumeStrategy,
)


class AssetType(Enum):
    """Tipos de ativos para classificação de estratégias."""

    LARGE_CAP = "large_cap"  # BTC, ETH
    MID_CAP = "mid_cap"  # BNB, ADA, SOL, XRP
    SMALL_CAP = "small_cap"  # Outros altcoins


class StrategyFactory:
    """Factory para criação automática de estratégias baseadas no tipo de ativo."""

    # Mapeamento de símbolos para tipos de ativos
    ASSET_CLASSIFICATION = {
        # Large Cap - Alta liquidez, menor volatilidade
        "BTC/USDT": AssetType.LARGE_CAP,
        "ETH/USDT": AssetType.LARGE_CAP,
        # Mid Cap - Volatilidade moderada, bons volumes
        "BNB/USDT": AssetType.MID_CAP,
        "ADA/USDT": AssetType.MID_CAP,
        "SOL/USDT": AssetType.MID_CAP,
        "XRP/USDT": AssetType.MID_CAP,
        "DOT/USDT": AssetType.MID_CAP,
        "MATIC/USDT": AssetType.MID_CAP,
        "AVAX/USDT": AssetType.MID_CAP,
        "LINK/USDT": AssetType.MID_CAP,
    }

    # Estratégias disponíveis por tipo de ativo
    STRATEGIES_BY_TYPE = {
        AssetType.LARGE_CAP: {
            "trend_following": TrendFollowingEMAStrategy,
            "mean_reversion": MeanReversionRSIStrategy,
            "swing_trading": SwingTradingStrategy,
        },
        AssetType.MID_CAP: {
            "breakout": BreakoutTradingStrategy,
            "momentum_volume": MomentumVolumeStrategy,
            "liquidity_scalping": LiquidityScalpingStrategy,
        },
    }

    @classmethod
    def get_asset_type(cls, symbol: str) -> AssetType:
        """Determina o tipo de ativo baseado no símbolo."""
        return cls.ASSET_CLASSIFICATION.get(symbol, AssetType.SMALL_CAP)

    @classmethod
    def create_strategy(cls, symbol: str, strategy_name: str, params: Dict = None) -> BaseStrategy:
        """
        Cria uma estratégia baseada no símbolo e nome da estratégia.

        Args:
            symbol: Par de trading (ex: BTC/USDT)
            strategy_name: Nome da estratégia
            params: Parâmetros específicos da estratégia

        Returns:
            Instância da estratégia configurada
        """
        asset_type = cls.get_asset_type(symbol)
        strategies = cls.STRATEGIES_BY_TYPE.get(asset_type, {})

        if strategy_name not in strategies:
            available = list(strategies.keys())
            raise ValueError(
                f"Estratégia '{strategy_name}' não disponível para {asset_type.value}. "
                f"Estratégias disponíveis: {available}"
            )

        strategy_class = strategies[strategy_name]
        return strategy_class(symbol, params or {})

    @classmethod
    def get_recommended_strategies(cls, symbol: str) -> Dict[str, Type[BaseStrategy]]:
        """Retorna as estratégias recomendadas para um símbolo."""
        asset_type = cls.get_asset_type(symbol)
        return cls.STRATEGIES_BY_TYPE.get(asset_type, {})

    @classmethod
    def list_all_strategies(cls) -> Dict[str, Dict[str, Type[BaseStrategy]]]:
        """Lista todas as estratégias disponíveis por tipo de ativo."""
        return {
            asset_type.value: strategies
            for asset_type, strategies in cls.STRATEGIES_BY_TYPE.items()
        }
