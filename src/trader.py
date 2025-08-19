import logging
import threading
import time
from typing import Dict, List

import pandas as pd
from colorama import Fore, Style, init

from account_tracker import AccountTracker
from exchange_manager import ExchangeManager
from market_monitor import MarketDatabase
from ultra_simple_websocket import UltraSimpleWebSocket
from risk_manager import RiskLevel, RiskManager, create_risk_profile
from strategies.base_strategy import BaseStrategy

init(autoreset=True)  # Inicializa colorama para cores no terminal


class TradingPair:
    """Gerencia o trading para um par específico com gestão de risco integrada."""

    def __init__(
        self,
        symbol: str,
        strategy: BaseStrategy,
        exchange_manager: ExchangeManager,
        amount: float,
    ):
        self.symbol = symbol
        self.strategy = strategy
        self.exchange = exchange_manager
        self.amount = amount
        self.in_position = False
        self.entry_price = 0
        self.total_profit = 0
        self.trades_count = 0
        self.last_update = None
        self.initial_balance = self.exchange.get_balance()
        self.trades_history = []

        # Gestão de risco (será injetado pelo MultiPairTrader)
        self.risk_manager = None
        self.current_trade_risk = None

        # Cache de dados de mercado
        self.last_price = 0
        self.last_volume = 0
        self.last_bid = 0
        self.last_ask = 0
        
        # Controle de análise em tempo real
        self._force_next_analysis = False

    def on_price_update(self, symbol: str, price: float, volume: float, bid: float, ask: float):
        """Callback chamado quando há atualização de preço via WebSocket - ANÁLISE EM TEMPO REAL."""
        if symbol == self.symbol:
            # Atualiza cache
            old_price = self.last_price
            self.last_price = price
            self.last_volume = volume
            self.last_bid = bid or 0
            self.last_ask = ask or 0

            # Calcula mudança percentual
            if old_price > 0:
                price_change_pct = abs((price - old_price) / old_price)
                
                # Análise em tempo real apenas para mudanças significativas
                if price_change_pct >= 0.001:  # 0.1% threshold
                    logging.info(
                        f"⚡ {Fore.CYAN}[REALTIME] {symbol}: ${price:.2f} "
                        f"({'+' if price > old_price else ''}{((price - old_price) / old_price * 100):+.2f}%) "
                        f"Vol: {volume:.0f}{Style.RESET_ALL}"
                    )
                    
                    # Trigger análise rápida se mudança significativa (>0.5%)
                    if price_change_pct >= 0.005 and not self.in_position:
                        self._quick_realtime_analysis(price, volume, bid, ask)

            # Verifica se posição deve ser fechada por stop-loss/take-profit
            if self.in_position and self.risk_manager:
                should_exit, reason = self.risk_manager.should_exit_position(symbol, price)
                if should_exit:
                    logging.info(f"{Fore.YELLOW}🚨 [REALTIME] {reason} - Executando saída{Style.RESET_ALL}")
                    self._execute_sell(price, reason)

    def _quick_realtime_analysis(self, price: float, volume: float, bid: float, ask: float):
        """Análise rápida em tempo real para mudanças de preço significativas."""
        try:
            # Análise básica de momentum
            spread = ask - bid if (ask > 0 and bid > 0) else 0
            spread_pct = (spread / price * 100) if price > 0 else 0
            
            # Volume analysis
            vol_indicator = "🔊 ALTO" if volume > self.last_volume * 1.5 else "🔉 NORMAL"
            
            # Spread analysis  
            spread_indicator = "💚 BAIXO" if spread_pct < 0.1 else "⚠️ ALTO"
            
            logging.info(
                f"📊 [QUICK-ANALYSIS] {self.symbol}: "
                f"Spread: {spread_pct:.3f}% {spread_indicator} | "
                f"Volume: {vol_indicator} | "
                f"Bid/Ask: ${bid:.2f}/${ask:.2f}"
            )
            
            # Se condições são muito favoráveis, considera entrada rápida
            if (spread_pct < 0.05 and  # spread muito baixo
                volume > self.last_volume * 2 and  # volume muito alto
                not self.in_position):  # não em posição
                
                logging.info(
                    f"⚡ {Fore.GREEN}[OPPORTUNITY] Condições favoráveis detectadas em tempo real "
                    f"para {self.symbol} - Triggering análise completa{Style.RESET_ALL}"
                )
                
                # Força análise completa na próxima iteração
                self._force_next_analysis = True
                
        except Exception as e:
            logging.error(f"❌ Erro na análise em tempo real: {e}")

    def update_market_data(self) -> pd.DataFrame:
        """Atualiza os dados do mercado."""
        logging.info(f"🔗 [API] Fazendo requisição para {self.symbol}")
        
        data = self.exchange.fetch_ohlcv(self.symbol)
        if data is None:
            logging.error(f"❌ [API] Falha ao obter dados para {self.symbol}")
            return None

        logging.info(f"📈 [API] Dados recebidos para {self.symbol}: {len(data)} candles")
        
        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["change"] = df.close.pct_change()
        
        # Log do preço atual
        current_price = df.iloc[-1]["close"]
        logging.info(f"💰 [PREÇO] {self.symbol}: ${current_price:.2f}")
        
        return df

    def execute_strategy(self, data: pd.DataFrame):
        """Executa a estratégia de trading com logs simplificados e claros."""
        if data is None:
            return

        signals = self.strategy.analyze(data)
        current_price = signals["metadata"]["current_price"]
        
        # Calcula variação de preço
        if "last_change" in signals["metadata"]:
            last_change = signals["metadata"]["last_change"]
        else:
            if len(data) >= 2:
                last_change = (current_price - data["close"].iloc[-2]) / data["close"].iloc[-2]
            else:
                last_change = 0.0

        # Atualiza cache se não temos dados de WebSocket
        if self.last_price == 0:
            self.last_price = current_price

        # Log simplificado e direto
        self._log_simple_analysis(current_price, last_change, signals)

        # Executa decisões de trading
        if not self.in_position and signals["should_buy"]:
            self._execute_buy_with_risk_check(current_price, last_change)
        elif self.in_position and signals["should_sell"]:
            self._execute_sell(current_price, "Sinal de venda da estratégia")
        else:
            action = "MANTER POSIÇÃO" if self.in_position else "AGUARDAR OPORTUNIDADE"
            logging.info(f"⏸️ {self.symbol}: {action}")

    def _log_simple_analysis(self, current_price: float, last_change: float, signals: dict):
        """Log simplificado da análise."""
        # Cor baseada na variação
        price_color = Fore.GREEN if last_change >= 0 else Fore.RED
        
        # Status da estratégia
        buy_signal = "🟢 COMPRA" if signals["should_buy"] else "⚪"
        sell_signal = "🔴 VENDA" if signals["should_sell"] else "⚪"
        position_status = "📍 EM POSIÇÃO" if self.in_position else "📊 ANALISANDO"
        
        logging.info(f"� [{self.symbol}] {position_status}")
        logging.info(f"   {price_color}💰 ${current_price:.2f} ({last_change*100:+.2f}%){Style.RESET_ALL}")
        logging.info(f"   📊 Sinais: {buy_signal} | {sell_signal}")
        
        # Mostra indicadores principais se disponíveis
        if "indicators" in signals["metadata"]:
            indicators = signals["metadata"]["indicators"]
            key_indicators = []
            
            # Seleciona indicadores principais baseado na estratégia
            if "rsi" in indicators:
                rsi_status = "🔴 OVERSOLD" if indicators["rsi"] < 30 else "🟢 OVERBOUGHT" if indicators["rsi"] > 70 else "⚪ NEUTRO"
                key_indicators.append(f"RSI: {indicators['rsi']:.1f} {rsi_status}")
            
            if "ema_fast" in indicators and "ema_slow" in indicators:
                trend = "📈 ALTA" if indicators["ema_fast"] > indicators["ema_slow"] else "📉 BAIXA"
                key_indicators.append(f"Tendência EMA: {trend}")
            
            if "volume_ratio" in indicators:
                vol_status = "🔊 ALTO" if indicators["volume_ratio"] > 1.0 else "🔉 BAIXO"
                key_indicators.append(f"Volume: {vol_status}")
            
            if key_indicators:
                logging.info(f"   📈 {' | '.join(key_indicators)}")

    def _log_status(self, current_price: float, last_change: float):
        """Loga o status atual com cores."""
        color = Fore.GREEN if last_change >= 0 else Fore.RED
        logging.info(
            f"{color}[{self.symbol}] Preço: {current_price:.2f} USDT | "
            f"Variação: {last_change*100:.2f}% | "
            f"Lucro Total: {self.total_profit*100:.2f}%{Style.RESET_ALL}"
        )

    def _execute_buy_with_risk_check(self, current_price: float, last_change: float):
        """Executa compra com verificação de gestão de risco."""
        if not self.risk_manager:
            # Fallback para comportamento original se não há risk manager
            self._execute_buy_legacy(current_price, last_change)
            return

        # Calcula stop-loss sugerido (3% abaixo do preço atual)
        suggested_stop_loss = current_price * 0.97

        # Calcula tamanho de posição baseado no risco
        position_size, sizing_details = self.risk_manager.calculate_position_size(
            self.symbol, current_price, suggested_stop_loss
        )

        # Valida se o trade pode ser executado
        can_trade, reason, trade_risk = self.risk_manager.validate_trade(
            self.symbol, current_price, position_size, suggested_stop_loss
        )

        if not can_trade:
            logging.warning(
                f"{Fore.YELLOW}⚠️ [{self.symbol}] Trade rejeitado: {reason}{Style.RESET_ALL}"
            )
            return

        logging.info(
            f"{Fore.YELLOW}[{self.symbol}] Sinal de compra detectado com gestão de risco:\n"
            f"   💰 Tamanho da posição: {position_size:.6f}\n"
            f"   💲 Valor da posição: ${position_size * current_price:.2f}\n"
            f"   🎯 Take Profit: ${trade_risk.take_profit:.2f}\n"
            f"   🛡️ Stop Loss: ${trade_risk.stop_loss:.2f}\n"
            f"   ⚠️ Risco máximo: ${trade_risk.risk_amount:.2f} ({trade_risk.risk_percentage:.2%})\n"
            f"   📊 Reward:Risk = 1:{trade_risk.reward_ratio:.2f}{Style.RESET_ALL}"
        )

        # Executa a ordem
        order = self.exchange.create_market_buy_order(self.symbol, position_size)
        if order:
            self.in_position = True
            self.entry_price = float(order["price"])
            self.amount = position_size  # Atualiza com tamanho calculado pelo risk manager
            self.trades_count += 1
            self.current_trade_risk = trade_risk

            # Registra no risk manager
            self.risk_manager.register_trade_entry(trade_risk)

            balance_after = self.exchange.get_balance()

            trade_info = {
                "type": "BUY",
                "price": self.entry_price,
                "amount": position_size,
                "cost": position_size * self.entry_price,
                "timestamp": pd.Timestamp.now(),
                "risk_amount": trade_risk.risk_amount,
                "expected_profit": trade_risk.expected_profit,
            }
            self.trades_history.append(trade_info)

            logging.info(
                f"{Fore.GREEN}[{self.symbol}] 💰 COMPRA REALIZADA (RISK-MANAGED):\n"
                f"   Preço: {self.entry_price:.6f} USDT\n"
                f"   Quantidade: {position_size:.6f}\n"
                f"   Custo total: {position_size * self.entry_price:.2f} USDT\n"
                f"   Saldo atual: {balance_after:.2f} USDT{Style.RESET_ALL}"
            )

    def _execute_buy_legacy(self, current_price: float, last_change: float):
        """Executa compra usando método legado (sem risk manager)."""
        balance_before = self.exchange.get_balance()

        logging.info(
            f"{Fore.YELLOW}[{self.symbol}] Sinal de compra detectado. "
            f"Queda: {last_change*100:.2f}%{Style.RESET_ALL}"
        )

        order = self.exchange.create_market_buy_order(self.symbol, self.amount)
        if order:
            self.in_position = True
            self.entry_price = float(order["price"])
            self.trades_count += 1

            balance_after = self.exchange.get_balance()
            cost = balance_before - balance_after

            trade_info = {
                "type": "BUY",
                "price": self.entry_price,
                "amount": self.amount,
                "cost": cost,
                "timestamp": pd.Timestamp.now(),
            }
            self.trades_history.append(trade_info)

            logging.info(
                f"{Fore.GREEN}[{self.symbol}] 💰 COMPRA REALIZADA:\n"
                f"   Preço: {self.entry_price:.2f} USDT\n"
                f"   Quantidade: {self.amount}\n"
                f"   Custo total: {cost:.2f} USDT\n"
                f"   Saldo atual: {balance_after:.2f} USDT{Style.RESET_ALL}"
            )

    def _execute_sell(self, current_price: float, reason: str = "Sinal de venda"):
        """Executa uma ordem de venda."""
        order = self.exchange.create_market_sell_order(self.symbol, self.amount)
        if order:
            exit_price = float(order["price"])
            profit = (exit_price - self.entry_price) / self.entry_price
            profit_usdt = (exit_price - self.entry_price) * self.amount
            self.total_profit += profit

            # Registra saída no risk manager
            if self.risk_manager:
                self.risk_manager.register_trade_exit(self.symbol, exit_price, profit_usdt)

            self.in_position = False
            self.current_trade_risk = None

            balance_after = self.exchange.get_balance()

            trade_info = {
                "type": "SELL",
                "price": exit_price,
                "amount": self.amount,
                "profit_usdt": profit_usdt,
                "profit_pct": profit * 100,
                "timestamp": pd.Timestamp.now(),
                "reason": reason,
            }
            self.trades_history.append(trade_info)

            color = Fore.GREEN if profit > 0 else Fore.RED
            emoji = "📈" if profit > 0 else "📉"
            logging.info(
                f"{color}[{self.symbol}] {emoji} VENDA REALIZADA ({reason}):\n"
                f"   Preço de venda: {exit_price:.6f} USDT\n"
                f"   Preço de compra: {self.entry_price:.6f} USDT\n"
                f"   Lucro/Prejuízo: {profit_usdt:.2f} USDT ({profit*100:.2f}%)\n"
                f"   Saldo atual: {balance_after:.2f} USDT\n"
                f"   Total acumulado: {self.total_profit*100:.2f}%{Style.RESET_ALL}"
            )

    def calculate_performance(self):
        """Calcula o desempenho do trading."""
        current_balance = self.exchange.get_balance()
        total_profit_usdt = current_balance - self.initial_balance
        total_profit_pct = (
            (total_profit_usdt / self.initial_balance) * 100 if self.initial_balance else 0
        )

        return {
            "symbol": self.symbol,
            "trades_count": self.trades_count,
            "total_profit_usdt": total_profit_usdt,
            "total_profit_pct": total_profit_pct,
            "current_balance": current_balance,
            "initial_balance": self.initial_balance,
            "in_position": self.in_position,
            "trades_history": self.trades_history,
        }


class MultiPairTrader:
    """Gerencia múltiplos pares de trading simultaneamente com monitoramento avançado."""

    def __init__(
        self, exchange_config: Dict, market_config: Dict = None, risk_config: Dict = None
    ):
        self.exchange_manager = ExchangeManager(exchange_config)
        self.trading_pairs: Dict[str, TradingPair] = {}
        self.running = False
        self.threads: List[threading.Thread] = []

        # Inicializa tracker de conta
        self.account_tracker = AccountTracker(self.exchange_manager)

        # Configurações de monitoramento de mercado
        self.market_config = market_config or {}
        self.market_database = MarketDatabase()
        self.market_monitor = None

        # Configurações de gestão de risco
        self.risk_config = risk_config or {}
        self.risk_manager = self._setup_risk_manager()

        # Tracking de performance
        self.start_time = time.time()
        self.last_summary_time = time.time()
        self.summary_interval = 120  # 2 minutos para teste

        logging.info(
            f"{Fore.GREEN}🚀 MultiPairTrader inicializado com "
            f"monitoramento avançado{Style.RESET_ALL}"
        )

    def _setup_risk_manager(self) -> RiskManager:
        """Configura o gerenciador de risco baseado no perfil."""
        risk_profile_name = self.risk_config.get("risk_profile", "moderate")

        # Mapeia string para enum
        risk_level_map = {
            "conservative": RiskLevel.CONSERVATIVE,
            "moderate": RiskLevel.MODERATE,
            "aggressive": RiskLevel.AGGRESSIVE,
        }

        risk_level = risk_level_map.get(risk_profile_name, RiskLevel.MODERATE)
        risk_params = create_risk_profile(risk_level)

        # Aplica configurações customizadas se fornecidas
        if "limits" in self.risk_config:
            limits = self.risk_config["limits"]
            risk_params.max_risk_per_trade = limits.get(
                "max_risk_per_trade", risk_params.max_risk_per_trade
            )
            risk_params.max_portfolio_risk = limits.get(
                "max_portfolio_risk", risk_params.max_portfolio_risk
            )
            risk_params.max_concurrent_trades = limits.get(
                "max_concurrent_trades", risk_params.max_concurrent_trades
            )
            risk_params.max_daily_loss = limits.get("max_daily_loss", risk_params.max_daily_loss)

        return RiskManager(self.exchange_manager, risk_params)

    def add_trading_pair(self, symbol: str, strategy: BaseStrategy, amount: float):
        """Adiciona um novo par para trading."""
        if symbol not in self.trading_pairs:
            # Cria trading pair com integração ao risk manager
            trading_pair = TradingPair(symbol, strategy, self.exchange_manager, amount)
            trading_pair.risk_manager = self.risk_manager  # Injeta risk manager

            self.trading_pairs[symbol] = trading_pair
            logging.info(f"{Fore.CYAN}Adicionado novo par de trading: {symbol}{Style.RESET_ALL}")

    def start(self):
        """Inicia o trading em todos os pares com monitoramento avançado."""
        self.running = True

        # Inicia monitoramento de mercado simplificado
        symbols = list(self.trading_pairs.keys())
        
        # WebSocket ultra-simplificado se habilitado
        if self.market_config.get("websocket_enabled", True):
            self.market_monitor = UltraSimpleWebSocket(symbols)
            
            # Adiciona callbacks para cada par
            for symbol, pair in self.trading_pairs.items():
                self.market_monitor.add_price_callback(symbol, pair.on_price_update)
                
            self.market_monitor.start_monitoring()
            logging.info(f"📡 WebSocket Ultra-Simples iniciado para {len(symbols)} símbolos")
        else:
            self.market_monitor = None
            logging.info("📡 WebSocket desabilitado, usando apenas análise periódica")

        # Inicia threads de trading
        for symbol, pair in self.trading_pairs.items():
            thread = threading.Thread(target=self._run_trading_pair, args=(pair,))
            thread.start()
            self.threads.append(thread)
            logging.info(
                f"{Fore.GREEN}🚀 Iniciado thread de trading para {symbol}{Style.RESET_ALL}"
            )

        # Thread para atualizações de trailing stop
        trail_thread = threading.Thread(target=self._update_trailing_stops_loop)
        trail_thread.start()
        self.threads.append(trail_thread)

    def is_running(self) -> bool:
        """Verifica se o trader está rodando."""
        return self.running and len([t for t in self.threads if t.is_alive()]) > 0

    def stop(self):
        """Para todas as operações de trading."""
        self.running = False

        # Para monitoramento de mercado
        if self.market_monitor:
            self.market_monitor.stop_monitoring()

        # Para threads
        for thread in self.threads:
            thread.join()

        # Cleanup do banco
        self.market_database.cleanup_old_data()

        logging.info(f"{Fore.YELLOW}Trading finalizado para todos os pares{Style.RESET_ALL}")

    def _update_trailing_stops_loop(self):
        """Loop para atualizar trailing stops."""
        while self.running:
            try:
                current_prices = {}
                for symbol in self.trading_pairs.keys():
                    if self.market_monitor:
                        price = self.market_monitor.get_current_price(symbol)
                        if price:
                            current_prices[symbol] = price

                if current_prices:
                    self.risk_manager.update_trailing_stops(current_prices)

                time.sleep(30)  # Atualiza a cada 30 segundos
            except Exception as e:
                logging.error(f"{Fore.RED}Erro no loop de trailing stop: {e}{Style.RESET_ALL}")
                time.sleep(30)

    def print_account_summary(self):
        """Imprime um resumo completo da conta, performance e gestão de risco."""
        total_balance = self.exchange_manager.get_balance()

        logging.info(f"\n{Fore.CYAN}{'='*60}")
        logging.info("📊 RESUMO COMPLETO DA CONTA 📊")
        logging.info(f"{'='*60}{Style.RESET_ALL}")
        logging.info(f"💰 Saldo total: {total_balance:.2f} USDT")

        # Resumo de risco
        risk_summary = self.risk_manager.get_risk_summary()
        risk_color = Fore.RED if risk_summary["portfolio_risk_pct"] > 0.05 else Fore.GREEN

        logging.info(f"\n{risk_color}🛡️ GESTÃO DE RISCO:")
        logging.info(f"   Risco do portfólio: {risk_summary['portfolio_risk_pct']:.2%}")
        logging.info(f"   Posições ativas: {risk_summary['active_positions']}")
        logging.info(
            f"   P&L diário: {risk_summary['daily_pnl']:.2f} USDT "
            f"({risk_summary['daily_pnl_pct']:.2%})"
        )
        logging.info(f"   Win Rate: {risk_summary['win_rate']:.1%}")
        logging.info(f"   Trades hoje: {risk_summary['daily_trades']}{Style.RESET_ALL}")

        total_profit_all = 0
        initial_balance_all = 0

        for symbol, pair in self.trading_pairs.items():
            perf = pair.calculate_performance()
            color = Fore.GREEN if perf["total_profit_pct"] >= 0 else Fore.RED
            emoji = "📈" if perf["total_profit_pct"] >= 0 else "📉"
            position_status = "🟢 SIM" if perf["in_position"] else "🔴 NÃO"

            total_profit_all += perf["total_profit_usdt"]
            initial_balance_all += perf["initial_balance"]

            logging.info(f"\n{color}{emoji} [{symbol}] Performance:")
            logging.info(f"   Trades realizados: {perf['trades_count']}")
            logging.info(
                f"   Lucro/Prejuízo: {perf['total_profit_usdt']:.2f} USDT "
                f"({perf['total_profit_pct']:.2f}%)"
            )
            logging.info(f"   Em posição: {position_status}")
            logging.info(f"   Saldo inicial: {perf['initial_balance']:.2f} USDT")

            # Informações de mercado se disponível
            if self.market_monitor:
                current_price = self.market_monitor.get_current_price(symbol)
                if current_price:
                    logging.info(f"   💹 Preço atual: ${current_price:.4f}")

                market_depth = self.market_monitor.get_market_depth(symbol)
                if market_depth and market_depth["bids"] and market_depth["asks"]:
                    best_bid = market_depth["bids"][0][0] if market_depth["bids"] else 0
                    best_ask = market_depth["asks"][0][0] if market_depth["asks"] else 0
                    spread = ((best_ask - best_bid) / best_ask * 100) if best_ask > 0 else 0
                    logging.info(f"   📊 Spread: {spread:.3f}%")

            logging.info(f"{Style.RESET_ALL}")

        # Resumo geral
        overall_profit_pct = (
            (total_profit_all / initial_balance_all * 100) if initial_balance_all else 0
        )
        overall_color = Fore.GREEN if overall_profit_pct >= 0 else Fore.RED

        logging.info(f"\n{overall_color}📊 PERFORMANCE GERAL:")
        logging.info(
            f"   Lucro/Prejuízo total: {total_profit_all:.2f} USDT ({overall_profit_pct:.2f}%)"
        )

        # Tempo de operação
        session_duration = (time.time() - self.start_time) / 3600  # horas
        logging.info(f"   ⏱️ Sessão ativa há: {session_duration:.1f} horas")

        logging.info(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

    def _run_trading_pair(self, pair: TradingPair):
        """Executa o loop de trading para um par específico com verificações de risco."""
        logging.info(f"� [THREAD] Iniciando trading para {pair.symbol}")
        
        while self.running:
            try:
                logging.info(f"� [CICLO] Iniciando análise para {pair.symbol}")
                
                # Verifica limites de risco antes de executar estratégia
                risk_summary = self.risk_manager.get_risk_summary()

                # Para trading se limite diário de perda atingido
                if (
                    abs(risk_summary["daily_pnl_pct"])
                    >= self.risk_manager.risk_params.max_daily_loss
                ):
                    logging.warning(
                        f"{Fore.RED}⚠️ Limite diário de perda atingido. "
                        f"Pausando trading para {pair.symbol}{Style.RESET_ALL}"
                    )
                    time.sleep(300)  # Pausa 5 minutos
                    continue

                # Atualiza dados e executa estratégia
                should_analyze = True
                
                # Verifica se deve fazer análise forçada por eventos em tempo real
                if pair._force_next_analysis:
                    logging.info(f"⚡ [REALTIME-TRIGGER] Análise forçada para {pair.symbol}")
                    pair._force_next_analysis = False
                    should_analyze = True
                
                if should_analyze:
                    logging.info(f"📊 [API] Coletando dados de mercado para {pair.symbol}...")
                    data = pair.update_market_data()
                    
                    if data is None:
                        logging.warning(f"⚠️ [ERRO] Sem dados de mercado para {pair.symbol}")
                        time.sleep(30)
                        continue
                    
                    logging.info(f"✅ [DADOS] Obtidos {len(data)} registros para {pair.symbol}")
                    pair.execute_strategy(data)
                else:
                    # Se não precisa analisar, apenas verifica preços via WebSocket
                    if self.market_monitor and self.market_monitor.is_connected():
                        current_price = self.market_monitor.get_current_price(pair.symbol)
                        if current_price:
                            logging.info(f"📡 [WEBSOCKET] {pair.symbol}: ${current_price:.2f}")

                # Log de resumo da conta a cada 5 minutos
                current_time = time.time()
                if current_time - self.last_summary_time >= self.summary_interval:
                    self.account_tracker.log_account_status()
                    self.account_tracker.log_performance_summary()
                    self.last_summary_time = current_time

                # Intervalo entre análises - menor se WebSocket ativo
                ws_connected = self.market_monitor and self.market_monitor.is_connected()
                sleep_interval = 30 if ws_connected else 60
                logging.info(f"⏱️ [CICLO] {pair.symbol} próxima análise em {sleep_interval}s...")
                time.sleep(sleep_interval)

            except Exception as e:
                logging.error(f"{Fore.RED}❌ [ERRO] {pair.symbol}: {str(e)}{Style.RESET_ALL}")
                time.sleep(60)
