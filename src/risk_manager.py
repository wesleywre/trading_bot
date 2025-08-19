"""
Sistema avançado de gestão de risco e capital para trading automatizado.
Implementa stop-loss, take-profit, position sizing e verificação de saldo.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from colorama import Fore, Style


class PositionSizeType(Enum):
    """Tipos de cálculo de tamanho de posição."""

    FIXED_AMOUNT = "fixed_amount"
    PERCENTAGE_BALANCE = "percentage_balance"
    RISK_BASED = "risk_based"
    KELLY_CRITERION = "kelly_criterion"


class RiskLevel(Enum):
    """Níveis de risco predefinidos."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass
class RiskParameters:
    """Parâmetros de risco configuráveis."""

    max_risk_per_trade: float = 0.01  # 1% do capital por trade (mais conservador)
    max_portfolio_risk: float = 0.05  # 5% do capital total em risco (mais conservador)
    max_concurrent_trades: int = 3
    max_daily_loss: float = 0.03  # 3% de perda máxima diária (mais conservador)

    # Stop-loss e take-profit
    default_stop_loss_pct: float = 0.02  # 2% stop-loss (mais conservador)
    default_take_profit_pct: float = 0.04  # 4% take-profit (R:R 1:2)

    # Parâmetros de trailing stop
    trailing_stop_enabled: bool = True
    trailing_stop_distance: float = 0.015  # 1.5% de distância (mais conservador)
    trailing_stop_step: float = 0.005  # 0.5% step para ajuste

    # Position sizing
    position_size_type: PositionSizeType = PositionSizeType.RISK_BASED
    fixed_position_size: float = 50.0  # Para FIXED_AMOUNT (reduzido)
    balance_percentage: float = 0.05  # 5% para PERCENTAGE_BALANCE (reduzido)


@dataclass
class TradeRisk:
    """Informações de risco para um trade específico."""

    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    risk_amount: float
    risk_percentage: float
    reward_ratio: float
    max_loss: float
    expected_profit: float


class RiskManager:
    """Gerenciador de risco e capital."""

    def __init__(self, exchange_manager, risk_params: RiskParameters = None):
        self.exchange = exchange_manager
        self.risk_params = risk_params or RiskParameters()

        # Tracking de posições ativas
        self.active_positions: Dict[str, TradeRisk] = {}
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.session_start_balance = self.exchange.get_balance()

        # Histórico de performance
        self.trade_history: List[Dict] = []
        self.win_rate = 0.0
        self.avg_win = 0.0
        self.avg_loss = 0.0

        logging.info(f"{Fore.GREEN}🛡️ Gerenciador de risco inicializado{Style.RESET_ALL}")

    def calculate_position_size(
        self, symbol: str, entry_price: float, stop_loss: float, confidence: float = 1.0
    ) -> Tuple[float, Dict]:
        """
        Calcula o tamanho ideal da posição baseado no tipo configurado.

        Args:
            symbol: Par de trading
            entry_price: Preço de entrada
            stop_loss: Preço do stop-loss
            confidence: Nível de confiança na trade (0-1)

        Returns:
            Tuple com (position_size, details)
        """
        current_balance = self.exchange.get_balance()
        risk_per_share = abs(entry_price - stop_loss)

        details = {
            "method": self.risk_params.position_size_type.value,
            "current_balance": current_balance,
            "risk_per_share": risk_per_share,
            "confidence": confidence,
        }

        if self.risk_params.position_size_type == PositionSizeType.FIXED_AMOUNT:
            position_size = self.risk_params.fixed_position_size / entry_price
            details["calculation"] = "fixed_amount / entry_price"

        elif self.risk_params.position_size_type == PositionSizeType.PERCENTAGE_BALANCE:
            position_value = current_balance * self.risk_params.balance_percentage
            position_size = position_value / entry_price
            details["calculation"] = "balance * percentage / entry_price"
            details["position_value"] = position_value

        elif self.risk_params.position_size_type == PositionSizeType.RISK_BASED:
            max_risk_amount = current_balance * self.risk_params.max_risk_per_trade
            position_size = max_risk_amount / risk_per_share
            details["calculation"] = "max_risk_amount / risk_per_share"
            details["max_risk_amount"] = max_risk_amount

        elif self.risk_params.position_size_type == PositionSizeType.KELLY_CRITERION:
            position_size = self._calculate_kelly_position(
                current_balance, entry_price, stop_loss, confidence
            )
            details["calculation"] = "kelly_criterion"

        # Ajusta por confiança
        position_size *= confidence

        # Verifica limites - MÁXIMO 10% do capital em uma posição
        max_position_value = current_balance * 0.10  # Máximo 10% do capital em uma posição
        max_position_size = max_position_value / entry_price

        if position_size > max_position_size:
            position_size = max_position_size
            details["limited_by"] = "max_position_value_10_percent"

        # Limite adicional: nunca mais que 5% do capital em risco real
        max_risk_value = current_balance * 0.05  # Máximo 5% de risco
        if (position_size * risk_per_share) > max_risk_value:
            position_size = max_risk_value / risk_per_share
            details["limited_by"] = "max_risk_5_percent"

        details["final_position_size"] = position_size
        details["position_value"] = position_size * entry_price
        details["actual_risk"] = position_size * risk_per_share
        details["risk_percentage"] = (position_size * risk_per_share) / current_balance

        return position_size, details

    def _calculate_kelly_position(
        self, balance: float, entry_price: float, stop_loss: float, confidence: float
    ) -> float:
        """Calcula position size usando critério de Kelly."""
        if not self.trade_history:
            # Sem histórico, usa risk-based
            max_risk_amount = balance * self.risk_params.max_risk_per_trade
            return max_risk_amount / abs(entry_price - stop_loss)

        # Calcula probabilidade de ganho e perda média
        wins = [t for t in self.trade_history[-50:] if t["profit"] > 0]
        losses = [t for t in self.trade_history[-50:] if t["profit"] <= 0]

        if not wins or not losses:
            return balance * 0.01 / entry_price  # Posição conservadora

        prob_win = len(wins) / len(self.trade_history[-50:])
        avg_win_pct = sum(t["profit_pct"] for t in wins) / len(wins)
        avg_loss_pct = abs(sum(t["profit_pct"] for t in losses) / len(losses))

        # Fórmula de Kelly: f = (bp - q) / b
        # b = avg_win / avg_loss, p = prob_win, q = prob_loss
        b = avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else 1
        kelly_fraction = (b * prob_win - (1 - prob_win)) / b

        # Aplica confiança e limita a 25% do capital
        kelly_fraction = max(0, min(0.25, kelly_fraction * confidence))

        return (balance * kelly_fraction) / entry_price

    def calculate_stop_loss_take_profit(
        self,
        symbol: str,
        entry_price: float,
        is_long: bool,
        custom_sl: float = None,
        custom_tp: float = None,
    ) -> Tuple[float, float]:
        """
        Calcula níveis de stop-loss e take-profit.

        Args:
            symbol: Par de trading
            entry_price: Preço de entrada
            is_long: True para posição comprada, False para vendida
            custom_sl: Stop-loss customizado (opcional)
            custom_tp: Take-profit customizado (opcional)

        Returns:
            Tuple (stop_loss, take_profit)
        """
        if custom_sl:
            stop_loss = custom_sl
        else:
            sl_distance = entry_price * self.risk_params.default_stop_loss_pct
            if is_long:
                stop_loss = entry_price - sl_distance
            else:
                stop_loss = entry_price + sl_distance

        if custom_tp:
            take_profit = custom_tp
        else:
            tp_distance = entry_price * self.risk_params.default_take_profit_pct
            if is_long:
                take_profit = entry_price + tp_distance
            else:
                take_profit = entry_price - tp_distance

        return stop_loss, take_profit

    def validate_trade(
        self, symbol: str, entry_price: float, position_size: float, stop_loss: float
    ) -> Tuple[bool, str, Optional[TradeRisk]]:
        """
        Valida se um trade pode ser executado baseado nas regras de risco.

        Returns:
            Tuple (can_trade, reason, trade_risk)
        """
        current_balance = self.exchange.get_balance()

        # 1. Verifica saldo suficiente
        position_value = position_size * entry_price
        if position_value > current_balance * 0.95:  # Reserva 5% para taxas
            return False, "Saldo insuficiente", None

        # 2. Verifica limite de trades concorrentes
        if len(self.active_positions) >= self.risk_params.max_concurrent_trades:
            return (
                False,
                f"Limite de {self.risk_params.max_concurrent_trades} trades concorrentes atingido",
                None,
            )

        # 3. Verifica risco por trade
        risk_amount = abs(entry_price - stop_loss) * position_size
        risk_percentage = risk_amount / current_balance

        if risk_percentage > self.risk_params.max_risk_per_trade:
            return (
                False,
                f"Risco por trade ({risk_percentage:.2%}) excede limite ({self.risk_params.max_risk_per_trade:.2%})",
                None,
            )

        # 4. Verifica risco total do portfólio
        total_portfolio_risk = sum(pos.risk_amount for pos in self.active_positions.values())
        new_total_risk = (total_portfolio_risk + risk_amount) / current_balance

        if new_total_risk > self.risk_params.max_portfolio_risk:
            return (
                False,
                f"Risco total do portfólio ({new_total_risk:.2%}) excederia limite ({self.risk_params.max_portfolio_risk:.2%})",
                None,
            )

        # 5. Verifica perda diária máxima
        daily_loss_pct = (
            abs(self.daily_pnl) / self.session_start_balance if self.daily_pnl < 0 else 0
        )
        if daily_loss_pct >= self.risk_params.max_daily_loss:
            return (
                False,
                f"Perda diária máxima ({self.risk_params.max_daily_loss:.2%}) atingida",
                None,
            )

        # 6. Cria objeto TradeRisk
        stop_loss, take_profit = self.calculate_stop_loss_take_profit(symbol, entry_price, True)

        trade_risk = TradeRisk(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            risk_amount=risk_amount,
            risk_percentage=risk_percentage,
            reward_ratio=abs(take_profit - entry_price) / abs(entry_price - stop_loss),
            max_loss=risk_amount,
            expected_profit=abs(take_profit - entry_price) * position_size,
        )

        return True, "Trade aprovado", trade_risk

    def register_trade_entry(self, trade_risk: TradeRisk):
        """Registra entrada em uma posição."""
        self.active_positions[trade_risk.symbol] = trade_risk
        self.daily_trades += 1

        logging.info(
            f"{Fore.GREEN}📈 Posição registrada para {trade_risk.symbol}:\n"
            f"   💰 Valor: ${trade_risk.position_size * trade_risk.entry_price:.2f}\n"
            f"   🎯 Take Profit: ${trade_risk.take_profit:.2f}\n"
            f"   🛡️ Stop Loss: ${trade_risk.stop_loss:.2f}\n"
            f"   ⚠️ Risco: ${trade_risk.risk_amount:.2f} ({trade_risk.risk_percentage:.2%})\n"
            f"   📊 R:R: 1:{trade_risk.reward_ratio:.2f}{Style.RESET_ALL}"
        )

    def register_trade_exit(self, symbol: str, exit_price: float, profit: float):
        """Registra saída de uma posição."""
        if symbol not in self.active_positions:
            return

        trade_risk = self.active_positions.pop(symbol)
        profit_pct = profit / (trade_risk.position_size * trade_risk.entry_price)

        # Atualiza estatísticas
        self.daily_pnl += profit

        trade_record = {
            "symbol": symbol,
            "entry_price": trade_risk.entry_price,
            "exit_price": exit_price,
            "position_size": trade_risk.position_size,
            "profit": profit,
            "profit_pct": profit_pct,
            "timestamp": time.time(),
            "duration_minutes": 0,  # Calcular se necessário
        }

        self.trade_history.append(trade_record)

        # Atualiza métricas de performance
        self._update_performance_metrics()

        result_color = Fore.GREEN if profit > 0 else Fore.RED
        result_emoji = "🎉" if profit > 0 else "😞"

        logging.info(
            f"{result_color}{result_emoji} Posição fechada para {symbol}:\n"
            f"   💰 Lucro/Prejuízo: ${profit:.2f} ({profit_pct:.2%})\n"
            f"   📊 Novo saldo: ${self.exchange.get_balance():.2f}\n"
            f"   📈 Win Rate: {self.win_rate:.1%}{Style.RESET_ALL}"
        )

    def _update_performance_metrics(self):
        """Atualiza métricas de performance."""
        if not self.trade_history:
            return

        recent_trades = self.trade_history[-100:]  # Últimas 100 trades

        wins = [t for t in recent_trades if t["profit"] > 0]
        losses = [t for t in recent_trades if t["profit"] <= 0]

        self.win_rate = len(wins) / len(recent_trades) if recent_trades else 0
        self.avg_win = sum(t["profit"] for t in wins) / len(wins) if wins else 0
        self.avg_loss = sum(t["profit"] for t in losses) / len(losses) if losses else 0

    def update_trailing_stops(self, current_prices: Dict[str, float]):
        """Atualiza trailing stops para posições ativas."""
        if not self.risk_params.trailing_stop_enabled:
            return

        for symbol, position in self.active_positions.items():
            if symbol not in current_prices:
                continue

            current_price = current_prices[symbol]

            # Calcula novo trailing stop (assumindo posição longa)
            trailing_distance = current_price * self.risk_params.trailing_stop_distance
            new_stop = current_price - trailing_distance

            # Atualiza apenas se o novo stop é melhor (mais alto para long)
            if new_stop > position.stop_loss:
                old_stop = position.stop_loss
                position.stop_loss = new_stop

                logging.info(
                    f"{Fore.CYAN}🔄 Trailing stop atualizado para {symbol}:\n"
                    f"   Preço atual: ${current_price:.2f}\n"
                    f"   Stop anterior: ${old_stop:.2f}\n"
                    f"   Novo stop: ${new_stop:.2f}{Style.RESET_ALL}"
                )

    def should_exit_position(self, symbol: str, current_price: float) -> Tuple[bool, str]:
        """Verifica se uma posição deve ser fechada."""
        if symbol not in self.active_positions:
            return False, "Posição não encontrada"

        position = self.active_positions[symbol]

        # Verifica stop-loss
        if current_price <= position.stop_loss:
            return True, f"Stop-loss ativado (${current_price:.2f} <= ${position.stop_loss:.2f})"

        # Verifica take-profit
        if current_price >= position.take_profit:
            return (
                True,
                f"Take-profit atingido (${current_price:.2f} >= ${position.take_profit:.2f})",
            )

        return False, "Posição mantida"

    def get_risk_summary(self) -> Dict:
        """Retorna resumo do risco atual."""
        current_balance = self.exchange.get_balance()
        total_portfolio_risk = sum(pos.risk_amount for pos in self.active_positions.values())
        portfolio_risk_pct = total_portfolio_risk / current_balance if current_balance > 0 else 0

        daily_pnl_pct = (
            self.daily_pnl / self.session_start_balance if self.session_start_balance > 0 else 0
        )

        return {
            "current_balance": current_balance,
            "session_start_balance": self.session_start_balance,
            "daily_pnl": self.daily_pnl,
            "daily_pnl_pct": daily_pnl_pct,
            "daily_trades": self.daily_trades,
            "active_positions": len(self.active_positions),
            "total_portfolio_risk": total_portfolio_risk,
            "portfolio_risk_pct": portfolio_risk_pct,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "risk_limits": {
                "max_risk_per_trade": self.risk_params.max_risk_per_trade,
                "max_portfolio_risk": self.risk_params.max_portfolio_risk,
                "max_concurrent_trades": self.risk_params.max_concurrent_trades,
                "max_daily_loss": self.risk_params.max_daily_loss,
            },
        }


def create_risk_profile(risk_level: RiskLevel) -> RiskParameters:
    """Cria perfil de risco predefinido."""
    if risk_level == RiskLevel.CONSERVATIVE:
        return RiskParameters(
            max_risk_per_trade=0.005,  # 0.5% - MUITO conservador
            max_portfolio_risk=0.02,  # 2% - MUITO conservador
            max_concurrent_trades=2,
            max_daily_loss=0.015,  # 1.5% - MUITO conservador
            default_stop_loss_pct=0.015,  # 1.5%
            default_take_profit_pct=0.03,  # 3% (R:R 1:2)
            position_size_type=PositionSizeType.RISK_BASED,
            balance_percentage=0.03,  # 3% máximo por posição
        )

    elif risk_level == RiskLevel.MODERATE:
        return RiskParameters(
            max_risk_per_trade=0.01,  # 1% - Conservador
            max_portfolio_risk=0.05,  # 5% - Conservador
            max_concurrent_trades=3,
            max_daily_loss=0.03,  # 3% - Conservador
            default_stop_loss_pct=0.02,  # 2%
            default_take_profit_pct=0.04,  # 4% (R:R 1:2)
            position_size_type=PositionSizeType.RISK_BASED,
            balance_percentage=0.05,  # 5% máximo por posição
        )

    elif risk_level == RiskLevel.AGGRESSIVE:
        return RiskParameters(
            max_risk_per_trade=0.02,  # 2% - Moderado (não mais 5%)
            max_portfolio_risk=0.08,  # 8% - Moderado (não mais 15%)
            max_concurrent_trades=4,  # Reduzido de 5 para 4
            max_daily_loss=0.05,  # 5% - Moderado (não mais 10%)
            default_stop_loss_pct=0.03,  # 3%
            default_take_profit_pct=0.06,  # 6% (R:R 1:2)
            position_size_type=PositionSizeType.RISK_BASED,  # Mudou de Kelly para Risk-based
            balance_percentage=0.08,  # 8% máximo por posição (não mais sem limite)
        )
