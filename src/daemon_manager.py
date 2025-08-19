"""
Sistema de gerenciamento para execução 24/7 do Trading Bot.
Inclui auto-recuperação, reconexão automática e monitoramento de saúde.
"""

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

import psutil
from dotenv import load_dotenv
from config_manager import ConfigManager, TradingProfile
from strategies import StrategyFactory
from trader import MultiPairTrader


class HealthMonitor:
    """Monitor de saúde do sistema."""
    
    def __init__(self):
        self.last_heartbeat = datetime.now()
        self.error_count = 0
        self.max_errors = 10
        self.restart_count = 0
        self.max_restarts = 5
        self.memory_threshold = 500  # MB
        self.cpu_threshold = 90  # %
        
    def heartbeat(self):
        """Registra batimento cardíaco do sistema."""
        self.last_heartbeat = datetime.now()
        
    def is_healthy(self) -> bool:
        """Verifica se o sistema está saudável."""
        # Verifica se houve heartbeat recente (últimos 5 minutos)
        if (datetime.now() - self.last_heartbeat).seconds > 300:
            logging.warning("⚠️ Sistema sem heartbeat há mais de 5 minutos")
            return False
            
        # Verifica uso de memória
        memory_usage = psutil.virtual_memory().used / 1024 / 1024  # MB
        if memory_usage > self.memory_threshold:
            logging.warning(f"⚠️ Alto uso de memória: {memory_usage:.1f}MB")
            
        # Verifica uso de CPU
        cpu_usage = psutil.cpu_percent(interval=1)
        if cpu_usage > self.cpu_threshold:
            logging.warning(f"⚠️ Alto uso de CPU: {cpu_usage:.1f}%")
            
        return True
        
    def log_error(self, error: Exception):
        """Registra erro no sistema."""
        self.error_count += 1
        logging.error(f"❌ Erro #{self.error_count}: {str(error)}")
        
        if self.error_count >= self.max_errors:
            logging.critical(f"🚨 Muitos erros ({self.error_count}), reinicialização necessária")
            
    def reset_errors(self):
        """Reseta contador de erros."""
        self.error_count = 0
        
    def can_restart(self) -> bool:
        """Verifica se ainda pode reiniciar o sistema."""
        return self.restart_count < self.max_restarts
        
    def log_restart(self):
        """Registra uma reinicialização."""
        self.restart_count += 1
        logging.info(f"🔄 Reinicialização #{self.restart_count}")


class TradingBotDaemon:
    """Daemon para execução contínua do Trading Bot."""
    
    def __init__(self, config_file: str = "config.yaml"):
        # Carrega variáveis de ambiente do .env PRIMEIRO
        load_dotenv()
        
        self.config_file = config_file
        self.running = False
        self.trader: Optional[MultiPairTrader] = None
        self.health_monitor = HealthMonitor()
        self.monitor_thread: Optional[threading.Thread] = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
        # Configura handlers para sinais do sistema
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handler para sinais de sistema."""
        logging.info(f"📡 Sinal recebido: {signum}")
        self.stop()
        
    def _setup_logging(self):
        """Configura sistema de logs rotativos."""
        from logging.handlers import RotatingFileHandler
        
        # Remove handlers existentes
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
            
        # Handler para arquivo com rotação
        file_handler = RotatingFileHandler(
            'trading_bot_daemon.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.INFO)
        
        # Handler para console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formato dos logs
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [DAEMON] %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Configura logger root
        logging.root.setLevel(logging.INFO)
        logging.root.addHandler(file_handler)
        logging.root.addHandler(console_handler)
        
        logging.info("🔧 Sistema de logging rotativo configurado")
        
    def _initialize_trader(self) -> bool:
        """Inicializa o trader com auto-recuperação."""
        try:
            logging.info("🔄 Inicializando Trading Bot...")
            
            # Inicializa gerenciador de configuração
            config_manager = ConfigManager(self.config_file)
            config = config_manager.load_config()
            
            logging.info("📊 Perfil de trading: moderate (daemon)")
            config_manager.set_trading_profile(TradingProfile.MODERATE)
            
            # Configurações
            exchange_config = config_manager.get_exchange_config()
            market_config = config_manager.get_market_monitoring_config()
            
            # Inicializa trader
            self.trader = MultiPairTrader(exchange_config, market_config, config)
            
            # Configura pares de trading
            asset_configs = config_manager.get_asset_configs()
            successful_pairs = 0
            
            for asset_config in asset_configs:
                try:
                    strategy = StrategyFactory.create_strategy(
                        symbol=asset_config.symbol,
                        strategy_name=asset_config.strategy,
                        params=asset_config.strategy_params,
                    )
                    
                    self.trader.add_trading_pair(
                        asset_config.symbol,
                        strategy,
                        asset_config.amount,
                    )
                    
                    successful_pairs += 1
                    logging.info(f"✅ {asset_config.symbol} configurado ({asset_config.strategy})")
                    
                except Exception as e:
                    logging.error(f"❌ Erro ao configurar {asset_config.symbol}: {e}")
                    
            if successful_pairs == 0:
                logging.error("❌ Nenhum par de trading foi configurado com sucesso")
                return False
                
            # Inicia trader
            self.trader.start()
            logging.info(f"🚀 Bot iniciado com {successful_pairs} pares de trading")
            
            self.reconnect_attempts = 0
            self.health_monitor.reset_errors()
            
            return True
            
        except Exception as e:
            logging.error(f"💥 Erro ao inicializar trader: {e}")
            self.health_monitor.log_error(e)
            return False
            
    def _monitor_health(self):
        """Thread de monitoramento de saúde."""
        logging.info("🔍 Monitor de saúde iniciado")
        
        while self.running:
            try:
                # Heartbeat
                self.health_monitor.heartbeat()
                
                # Verifica saúde geral
                if not self.health_monitor.is_healthy():
                    logging.warning("⚠️ Sistema não está saudável")
                    
                # Verifica se o trader ainda está rodando
                if self.trader and not self.trader.is_running():
                    logging.error("❌ Trader parou de funcionar, tentando reiniciar...")
                    self._restart_trader()
                    
                # Log de status a cada 10 minutos
                if datetime.now().minute % 10 == 0 and datetime.now().second == 0:
                    self._log_status()
                    
                time.sleep(60)  # Verifica a cada minuto
                
            except Exception as e:
                logging.error(f"❌ Erro no monitor de saúde: {e}")
                time.sleep(60)
                
        logging.info("🔍 Monitor de saúde finalizado")
        
    def _restart_trader(self) -> bool:
        """Reinicia o trader em caso de falha."""
        if not self.health_monitor.can_restart():
            logging.critical("🚨 Limite de reinicializações atingido, parando daemon")
            self.stop()
            return False
            
        try:
            logging.info("🔄 Reiniciando trader...")
            self.health_monitor.log_restart()
            
            # Para trader atual
            if self.trader:
                self.trader.stop()
                self.trader = None
                
            # Aguarda um pouco
            time.sleep(30)
            
            # Tenta reconectar
            if self._try_reconnect():
                logging.info("✅ Trader reiniciado com sucesso")
                return True
            else:
                logging.error("❌ Falha ao reiniciar trader")
                return False
                
        except Exception as e:
            logging.error(f"💥 Erro ao reiniciar trader: {e}")
            self.health_monitor.log_error(e)
            return False
            
    def _try_reconnect(self) -> bool:
        """Tenta reconectar com backoff exponencial."""
        while self.reconnect_attempts < self.max_reconnect_attempts and self.running:
            self.reconnect_attempts += 1
            wait_time = min(60 * (2 ** self.reconnect_attempts), 1800)  # Max 30min
            
            logging.info(f"🔄 Tentativa de reconexão #{self.reconnect_attempts}/{self.max_reconnect_attempts}")
            logging.info(f"⏱️ Aguardando {wait_time}s antes da próxima tentativa...")
            
            time.sleep(wait_time)
            
            if self._initialize_trader():
                logging.info("✅ Reconexão bem-sucedida")
                return True
                
        logging.error("❌ Todas as tentativas de reconexão falharam")
        return False
        
    def _log_status(self):
        """Registra status do sistema."""
        try:
            # Info do sistema
            memory = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=1)
            
            # Info do trader
            active_pairs = len(self.trader.trading_pairs) if self.trader else 0
            
            logging.info(
                f"📊 STATUS: "
                f"CPU: {cpu:.1f}% | "
                f"RAM: {memory.percent:.1f}% | "
                f"Pares ativos: {active_pairs} | "
                f"Erros: {self.health_monitor.error_count} | "
                f"Reinicializações: {self.health_monitor.restart_count}"
            )
            
            # Log resumo da conta se disponível
            if self.trader:
                self.trader.print_account_summary()
                
        except Exception as e:
            logging.error(f"❌ Erro ao registrar status: {e}")
            
    def start(self):
        """Inicia o daemon."""
        if self.running:
            logging.warning("⚠️ Daemon já está rodando")
            return
            
        logging.info("🚀 Iniciando Trading Bot Daemon...")
        self._setup_logging()
        
        self.running = True
        
        # Tenta inicializar o trader
        if not self._initialize_trader():
            if not self._try_reconnect():
                logging.critical("🚨 Falha ao inicializar o sistema")
                self.running = False
                return
                
        # Inicia monitor de saúde
        self.monitor_thread = threading.Thread(target=self._monitor_health, daemon=True)
        self.monitor_thread.start()
        
        logging.info("✅ Trading Bot Daemon iniciado com sucesso")
        logging.info("📡 Sistema rodando em modo 24/7")
        
        # Loop principal
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("⌨️ Interrupção manual detectada")
            
        self.stop()
        
    def stop(self):
        """Para o daemon graciosamente."""
        if not self.running:
            return
            
        logging.info("⏹️ Parando Trading Bot Daemon...")
        self.running = False
        
        # Para trader
        if self.trader:
            self.trader.stop()
            
        # Aguarda thread de monitoramento
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10)
            
        logging.info("✅ Trading Bot Daemon parado")
        
    def status(self) -> Dict:
        """Retorna status atual do daemon."""
        return {
            'running': self.running,
            'trader_active': self.trader.is_running() if self.trader else False,
            'error_count': self.health_monitor.error_count,
            'restart_count': self.health_monitor.restart_count,
            'last_heartbeat': self.health_monitor.last_heartbeat,
            'reconnect_attempts': self.reconnect_attempts,
        }


def main():
    """Função principal do daemon."""
    daemon = TradingBotDaemon()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'start':
            daemon.start()
        elif command == 'status':
            status = daemon.status()
            print("📊 Status do Trading Bot Daemon:")
            for key, value in status.items():
                print(f"  {key}: {value}")
        else:
            print("❓ Comando inválido. Use: start, status")
    else:
        # Modo interativo
        daemon.start()


if __name__ == "__main__":
    main()
