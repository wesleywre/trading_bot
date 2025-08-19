import logging
from datetime import datetime
from typing import Dict

from colorama import Fore, Style


class AccountTracker:
    """Monitora e reporta informações claras sobre a conta de trading."""

    def __init__(self, exchange_manager):
        self.exchange = exchange_manager
        self.initial_balance = self.exchange.get_balance("USDT")
        self.trades_log = []
        self.positions = {}  # {symbol: {amount, entry_price, unrealized_pnl}}

        # Registra balanço inicial
        logging.info(f"💰 [CONTA] Balanço inicial: ${self.initial_balance:,.2f} USDT")

    def get_account_summary(self) -> Dict:
        """Retorna resumo completo da conta."""
        current_balance = self.exchange.get_balance("USDT")
        total_invested = sum(pos["amount"] * pos["entry_price"] for pos in self.positions.values())
        unrealized_pnl = sum(pos.get("unrealized_pnl", 0) for pos in self.positions.values())
        realized_pnl = sum(trade["profit"] for trade in self.trades_log)
        total_pnl = realized_pnl + unrealized_pnl

        return {
            "current_balance": current_balance,
            "initial_balance": self.initial_balance,
            "total_invested": total_invested,
            "available_balance": current_balance - total_invested,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
            "roi_percent": (
                (total_pnl / self.initial_balance) * 100 if self.initial_balance > 0 else 0
            ),
            "total_trades": len(self.trades_log),
            "active_positions": len(self.positions),
        }

    def log_account_status(self):
        """Loga status da conta de forma clara e direta."""
        summary = self.get_account_summary()

        # Cor baseada no lucro/prejuízo
        pnl_color = Fore.GREEN if summary["total_pnl"] >= 0 else Fore.RED
        roi_color = Fore.GREEN if summary["roi_percent"] >= 0 else Fore.RED

        logging.info("=" * 80)
        logging.info(f"{Fore.CYAN}💼 RESUMO DA CONTA{Style.RESET_ALL}")
        logging.info(f"   💰 Balanço Atual: ${summary['current_balance']:,.2f} USDT")
        logging.info(f"   📊 Valor Investido: ${summary['total_invested']:,.2f} USDT")
        logging.info(f"   💵 Disponível: ${summary['available_balance']:,.2f} USDT")
        pnl_text = f"{pnl_color}📈 L&P Total: ${summary['total_pnl']:+,.2f} USDT"
        logging.info(f"   {pnl_text}{Style.RESET_ALL}")
        logging.info(f"   {roi_color}🎯 Retorno: {summary['roi_percent']:+.2f}%{Style.RESET_ALL}")
        logging.info(f"   📋 Trades Realizados: {summary['total_trades']}")
        logging.info(f"   🔄 Posições Ativas: {summary['active_positions']}")
        logging.info("=" * 80)

    def log_trade_entry(self, symbol: str, amount: float, price: float, trade_type: str):
        """Registra entrada em uma posição."""
        timestamp = datetime.now()

        # Registra posição
        self.positions[symbol] = {
            "amount": amount,
            "entry_price": price,
            "entry_time": timestamp,
            "unrealized_pnl": 0,
        }

        # Log da entrada
        value = amount * price
        logging.info(f"🚀 [ENTRADA] {symbol}")
        logging.info(f"   📊 Tipo: {trade_type}")
        logging.info(f"   💰 Quantidade: {amount:.6f}")
        logging.info(f"   💵 Preço: ${price:.2f}")
        logging.info(f"   💲 Valor Total: ${value:.2f}")
        logging.info(f"   ⏰ Horário: {timestamp.strftime('%H:%M:%S')}")

    def log_trade_exit(self, symbol: str, exit_price: float, reason: str):
        """Registra saída de uma posição."""
        if symbol not in self.positions:
            logging.warning(f"⚠️ Tentativa de sair de posição inexistente: {symbol}")
            return

        position = self.positions[symbol]
        amount = position["amount"]
        entry_price = position["entry_price"]
        profit = (exit_price - entry_price) * amount
        profit_percent = (profit / (entry_price * amount)) * 100

        # Registra trade completo
        trade_record = {
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "amount": amount,
            "profit": profit,
            "profit_percent": profit_percent,
            "reason": reason,
            "timestamp": datetime.now(),
        }
        self.trades_log.append(trade_record)

        # Remove posição
        del self.positions[symbol]

        # Log da saída
        profit_color = Fore.GREEN if profit >= 0 else Fore.RED

        logging.info(f"💰 [SAÍDA] {symbol}")
        logging.info(f"   📊 Motivo: {reason}")
        logging.info(f"   💰 Quantidade: {amount:.6f}")
        logging.info(f"   📈 Preço Entrada: ${entry_price:.2f}")
        logging.info(f"   📉 Preço Saída: ${exit_price:.2f}")
        profit_text = f"{profit_color}💵 Lucro/Prejuízo: ${profit:+.2f}"
        profit_pct = f"({profit_percent:+.1f}%){Style.RESET_ALL}"
        logging.info(f"   {profit_text} {profit_pct}")
        logging.info(f"   ⏰ Horário: {trade_record['timestamp'].strftime('%H:%M:%S')}")

    def update_unrealized_pnl(self, symbol: str, current_price: float):
        """Atualiza P&L não realizado de uma posição."""
        if symbol in self.positions:
            position = self.positions[symbol]
            entry_price = position["entry_price"]
            amount = position["amount"]
            unrealized_pnl = (current_price - entry_price) * amount
            position["unrealized_pnl"] = unrealized_pnl

    def log_position_status(self, symbol: str, current_price: float):
        """Loga status de uma posição específica."""
        if symbol not in self.positions:
            return

        self.update_unrealized_pnl(symbol, current_price)
        position = self.positions[symbol]

        unrealized_pnl = position["unrealized_pnl"]
        position_value = position["entry_price"] * position["amount"]
        unrealized_percent = (unrealized_pnl / position_value) * 100
        pnl_color = Fore.GREEN if unrealized_pnl >= 0 else Fore.RED

        logging.info(f"📍 [POSIÇÃO] {symbol}")
        logging.info(f"   💰 Quantidade: {position['amount']:.6f}")
        logging.info(f"   📈 Preço Entrada: ${position['entry_price']:.2f}")
        logging.info(f"   📊 Preço Atual: ${current_price:.2f}")
        pnl_text = f"{pnl_color}💵 P&L Não Realizado: ${unrealized_pnl:+.2f}"
        pnl_pct = f"({unrealized_percent:+.1f}%){Style.RESET_ALL}"
        logging.info(f"   {pnl_text} {pnl_pct}")

    def get_trading_performance(self) -> Dict:
        """Retorna estatísticas de performance de trading."""
        if not self.trades_log:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "avg_profit": 0,
                "max_profit": 0,
                "max_loss": 0,
            }

        winning_trades = [t for t in self.trades_log if t["profit"] > 0]
        losing_trades = [t for t in self.trades_log if t["profit"] < 0]

        return {
            "total_trades": len(self.trades_log),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": (len(winning_trades) / len(self.trades_log)) * 100,
            "avg_profit": sum(t["profit"] for t in self.trades_log) / len(self.trades_log),
            "max_profit": max(t["profit"] for t in self.trades_log),
            "max_loss": min(t["profit"] for t in self.trades_log),
        }

    def log_performance_summary(self):
        """Loga resumo de performance."""
        perf = self.get_trading_performance()

        if perf["total_trades"] == 0:
            logging.info("📊 [PERFORMANCE] Nenhum trade realizado ainda")
            return

        win_rate_color = Fore.GREEN if perf["win_rate"] >= 50 else Fore.RED

        logging.info("📊 [PERFORMANCE] Estatísticas de Trading:")
        logging.info(f"   📈 Trades Vencedores: {perf['winning_trades']}")
        logging.info(f"   📉 Trades Perdedores: {perf['losing_trades']}")
        win_text = f"{win_rate_color}🎯 Taxa de Acerto: {perf['win_rate']:.1f}%"
        logging.info(f"   {win_text}{Style.RESET_ALL}")
        logging.info(f"   💰 Lucro Médio: ${perf['avg_profit']:+.2f}")
        logging.info(f"   🚀 Maior Lucro: ${perf['max_profit']:+.2f}")
        logging.info(f"   💔 Maior Perda: ${perf['max_loss']:+.2f}")
