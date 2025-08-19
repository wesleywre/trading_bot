"""
Sistema de configuração avançado para o trading bot.
Suporta perfis de configuração, validação e configurações dinâmicas.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv


class TradingProfile(Enum):
    """Perfis de trading pré-configurados."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    SCALPING = "scalping"


@dataclass
class AssetConfig:
    """Configuração específica de um ativo."""

    symbol: str
    strategy: str
    strategy_params: Dict[str, Any]
    amount: float
    asset_type: str  # large_cap, mid_cap, small_cap


@dataclass
class RiskConfig:
    """Configuração de gestão de risco."""

    max_risk_per_trade: float
    max_portfolio_risk: float
    max_concurrent_trades: int
    max_daily_loss: float
    stop_loss_percentage: float
    take_profit_percentage: float


class ConfigManager:
    """Gerenciador central de configurações."""

    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        self.trading_profile: TradingProfile = TradingProfile.MODERATE
        load_dotenv()

    def load_config(self) -> Dict[str, Any]:
        """Carrega configuração do arquivo YAML."""
        try:
            with open(self.config_file, "r", encoding="utf-8") as file:
                config_content = file.read()

            # Substitui variáveis de ambiente
            config_content = self._substitute_env_vars(config_content)
            self.config = yaml.safe_load(config_content)

            # Valida configuração
            self._validate_config()

            logging.info(f"✅ Configuração carregada de {self.config_file}")
            return self.config

        except Exception as e:
            logging.error(f"❌ Erro ao carregar configuração: {e}")
            raise

    def _substitute_env_vars(self, content: str) -> str:
        """Substitui variáveis de ambiente no formato ${VAR_NAME}."""
        import re

        def replace_env_var(match):
            var_name = match.group(1)
            return os.getenv(var_name, "")

        return re.sub(r"\$\{([^}]+)\}", replace_env_var, content)

    def _validate_config(self) -> None:
        """Valida a configuração carregada."""
        required_sections = ["exchange", "trading_pairs", "risk_management"]

        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Seção obrigatória '{section}' não encontrada na configuração")

        # Valida pares de trading
        for pair in self.config["trading_pairs"]:
            required_pair_fields = ["symbol", "strategy", "amount"]
            for field in required_pair_fields:
                if field not in pair:
                    raise ValueError(
                        f"Campo obrigatório '{field}' não encontrado no par {pair.get('symbol', 'unknown')}"
                    )

    def get_asset_configs(self) -> List[AssetConfig]:
        """Retorna lista de configurações de ativos."""
        assets = []

        for pair_config in self.config["trading_pairs"]:
            # Determina tipo de ativo baseado no símbolo
            symbol = pair_config["symbol"]
            asset_type = self._determine_asset_type(symbol)

            asset = AssetConfig(
                symbol=symbol,
                strategy=pair_config["strategy"],
                strategy_params=pair_config.get("strategy_params", {}),
                amount=pair_config["amount"],
                asset_type=asset_type,
            )
            assets.append(asset)

        return assets

    def _determine_asset_type(self, symbol: str) -> str:
        """Determina o tipo de ativo baseado no símbolo."""
        large_caps = ["BTC/USDT", "ETH/USDT"]
        mid_caps = ["BNB/USDT", "ADA/USDT", "SOL/USDT", "XRP/USDT", "DOT/USDT", "MATIC/USDT"]

        if symbol in large_caps:
            return "large_cap"
        elif symbol in mid_caps:
            return "mid_cap"
        else:
            return "small_cap"

    def get_risk_config(self, asset_type: str = None) -> RiskConfig:
        """Retorna configuração de risco, opcionalmente específica para tipo de ativo."""
        risk_section = self.config["risk_management"]

        # Configurações base
        base_config = RiskConfig(
            max_risk_per_trade=risk_section["limits"]["max_risk_per_trade"],
            max_portfolio_risk=risk_section["limits"]["max_portfolio_risk"],
            max_concurrent_trades=risk_section["limits"]["max_concurrent_trades"],
            max_daily_loss=risk_section["limits"]["max_daily_loss"],
            stop_loss_percentage=risk_section["stop_loss"].get("default_percentage", 0.03),
            take_profit_percentage=risk_section["take_profit"].get("default_percentage", 0.06),
        )

        # Ajusta baseado no tipo de ativo
        if asset_type:
            stop_loss_section = risk_section.get("stop_loss", {})
            take_profit_section = risk_section.get("take_profit", {})

            if asset_type == "large_cap":
                base_config.stop_loss_percentage = stop_loss_section.get(
                    "large_cap_percentage", 0.025
                )
                base_config.take_profit_percentage = take_profit_section.get(
                    "large_cap_percentage", 0.05
                )
            elif asset_type == "mid_cap":
                base_config.stop_loss_percentage = stop_loss_section.get(
                    "mid_cap_percentage", 0.035
                )
                base_config.take_profit_percentage = take_profit_section.get(
                    "mid_cap_percentage", 0.08
                )

        return base_config

    def set_trading_profile(self, profile: TradingProfile) -> None:
        """Define o perfil de trading e ajusta configurações."""
        self.trading_profile = profile

        # Ajusta configurações baseado no perfil
        if profile == TradingProfile.CONSERVATIVE:
            self._apply_conservative_settings()
        elif profile == TradingProfile.AGGRESSIVE:
            self._apply_aggressive_settings()
        elif profile == TradingProfile.SCALPING:
            self._apply_scalping_settings()

    def _apply_conservative_settings(self) -> None:
        """Aplica configurações conservadoras."""
        risk_section = self.config["risk_management"]
        risk_section["limits"]["max_risk_per_trade"] = 0.01  # 1%
        risk_section["limits"]["max_portfolio_risk"] = 0.05  # 5%
        risk_section["limits"]["max_concurrent_trades"] = 2

        # Reduz update interval
        self.config["general"]["update_interval_seconds"] = 120

    def _apply_aggressive_settings(self) -> None:
        """Aplica configurações agressivas."""
        risk_section = self.config["risk_management"]
        risk_section["limits"]["max_risk_per_trade"] = 0.03  # 3%
        risk_section["limits"]["max_portfolio_risk"] = 0.12  # 12%
        risk_section["limits"]["max_concurrent_trades"] = 8

        # Aumenta update interval
        self.config["general"]["update_interval_seconds"] = 30

    def _apply_scalping_settings(self) -> None:
        """Aplica configurações para scalping."""
        risk_section = self.config["risk_management"]
        risk_section["limits"]["max_risk_per_trade"] = 0.005  # 0.5%
        risk_section["limits"]["max_concurrent_trades"] = 10

        # Update muito rápido para scalping
        self.config["general"]["update_interval_seconds"] = 10

    def get_exchange_config(self) -> Dict[str, Any]:
        """Retorna configuração da exchange."""
        return self.config["exchange"]

    def get_market_monitoring_config(self) -> Dict[str, Any]:
        """Retorna configuração de monitoramento de mercado."""
        return self.config.get("market_monitoring", {})

    def get_logging_config(self) -> Dict[str, Any]:
        """Retorna configuração de logging."""
        return self.config.get(
            "logging",
            {
                "level": "INFO",
                "format": "%(asctime)s - %(levelname)s - %(message)s",
                "file": "trading_bot.log",
            },
        )

    def save_config(self, filename: str = None) -> None:
        """Salva a configuração atual em arquivo."""
        target_file = filename or f"{self.config_file}.backup"

        try:
            with open(target_file, "w", encoding="utf-8") as file:
                yaml.dump(self.config, file, default_flow_style=False, allow_unicode=True)
            logging.info(f"✅ Configuração salva em {target_file}")
        except Exception as e:
            logging.error(f"❌ Erro ao salvar configuração: {e}")

    def create_default_config(self) -> Dict[str, Any]:
        """Cria uma configuração padrão."""
        default_config = {
            "exchange": {
                "apiKey": "${BINANCE_API_KEY}",
                "secret": "${BINANCE_API_SECRET}",
                "enableRateLimit": True,
                "testnet": True,
                "options": {
                    "defaultType": "spot",
                    "adjustForTimeDifference": True,
                    "createMarketBuyOrderRequiresPrice": False,
                },
            },
            "trading_pairs": [
                {
                    "symbol": "BTC/USDT",
                    "strategy": "trend_following",
                    "strategy_params": {"ema_fast": 50, "ema_slow": 200, "volume_multiplier": 1.3},
                    "amount": 0.001,
                }
            ],
            "risk_management": {
                "risk_profile": "moderate",
                "position_sizing": {"type": "risk_based"},
                "limits": {
                    "max_risk_per_trade": 0.02,
                    "max_portfolio_risk": 0.08,
                    "max_concurrent_trades": 3,
                    "max_daily_loss": 0.05,
                },
                "stop_loss": {"default_percentage": 0.03},
                "take_profit": {"default_percentage": 0.06},
            },
            "general": {
                "update_interval_seconds": 60,
                "show_summary_interval_minutes": 5,
                "max_concurrent_trades": 3,
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(levelname)s - %(message)s",
                "file": "trading_bot.log",
            },
        }

        return default_config
