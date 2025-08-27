"""Exchange management module for trading bot.

This module provides:
- ExchangeManager: manages connection to exchange and trading operations
- Support for both real trading and simulation mode
- Market data fetching and order execution functionality
"""

import logging
from typing import Any, Dict

import ccxt

from market_simulator import get_simulated_ohlcv


class ExchangeManager:
    """Gerencia a conexão com a exchange e operações de trading."""

    def __init__(self, exchange_config: Dict[str, Any]):
        self.simulation_mode = False
        try:
            # Verifica se temos chaves de API válidas
            api_key = exchange_config.get("apiKey", "")
            secret = exchange_config.get("secret", "")

            logging.info(
                f"🔑 [CONFIG] API Key: {api_key[:10]}..."
                if api_key
                else "🔑 [CONFIG] API Key: (vazia)"
            )
            logging.info(
                f"🔐 [CONFIG] Secret: {secret[:10]}..."
                if secret
                else "🔐 [CONFIG] Secret: (vazia)"
            )

            # Força conexão real com Testnet se as chaves estão configuradas
            if not api_key or not secret or "your_" in api_key or "your_" in secret:
                logging.warning("🟡 Chaves de API não configuradas, executando em modo simulação")
                self.simulation_mode = True
                self.exchange = None
            else:
                logging.info("🔗 [CONNECT] Conectando à Binance testnet...")

                # Garante que está em modo testnet
                exchange_config["testnet"] = True
                exchange_config["sandbox"] = True

                self.exchange = ccxt.binance(exchange_config)

                # Testa a conexão buscando o saldo
                balance = self.exchange.fetch_balance()
                logging.info(
                    f"🟢 [CONNECT] Conectado à Binance Testnet - Saldo USDT: {balance['total'].get('USDT', 0)}"
                )

                # Força modo real (não simulação)
                self.simulation_mode = False

        except Exception as e:
            logging.error(f"� [CONNECT] Erro na conexão com exchange: {e}")
            # Se falhar, ainda assim tenta conectar mas avisa o usuário
            logging.warning("⚠️  Tentando continuar em modo real mesmo com erro...")
            self.simulation_mode = False
            try:
                exchange_config["testnet"] = True
                self.exchange = ccxt.binance(exchange_config)
            except:
                logging.error("❌ Falha total na conexão, usando modo simulação")
                self.simulation_mode = True
                self.exchange = None

        self.trading_fees = {}
        self._load_trading_fees()

    def _load_trading_fees(self):
        """Carrega as taxas de trading para todos os pares."""
        if self.simulation_mode:
            # Taxas padrão para simulação
            self.trading_fees = {
                "BTC/USDT": 0.001,
                "ETH/USDT": 0.001,
                "BNB/USDT": 0.001,
                "ADA/USDT": 0.001,
                "SOL/USDT": 0.001,
                "XRP/USDT": 0.001,
            }
            return

        try:
            markets = self.exchange.load_markets()
            for symbol in markets:
                self.trading_fees[symbol] = markets[symbol].get("taker", 0.001)
        except Exception as e:
            logging.error(f"\033[91mErro ao carregar taxas de trading: {str(e)}\033[0m")

    def get_balance(self, currency: str = "USDT") -> float:
        """Retorna o saldo de uma moeda específica."""
        # Sempre tenta buscar saldo real primeiro
        if self.exchange is not None:
            try:
                balance = self.exchange.fetch_balance()
                real_balance = float(balance["total"].get(currency, 0))
                logging.info(f"💰 [REAL] Saldo {currency}: {real_balance}")
                return real_balance
            except Exception as e:
                logging.error(f"🔴 Erro ao buscar saldo real de {currency}: {str(e)}")

        # Só usa simulação se não conseguir conectar
        if self.simulation_mode:
            logging.warning(f"⚠️  [SIMULAÇÃO] Usando saldo simulado de {currency}: 10000.0")
            return 10000.0  # $10,000 USDT simulados

        # Se chegou aqui, é porque não está em simulação mas teve erro
        logging.error(f"❌ Falha ao buscar saldo real de {currency}, retornando 0")
        return 0.0

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 1000):
        """Busca dados OHLCV do mercado."""
        if self.simulation_mode:
            # Retorna dados simulados
            logging.info(f"📊 [SIMULAÇÃO] Buscando dados OHLCV para {symbol}")
            return get_simulated_ohlcv(symbol, timeframe, limit)

        try:
            return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except Exception as e:
            logging.error(f"\033[91mErro ao buscar dados OHLCV para {symbol}: {str(e)}\033[0m")
            return None

    def create_market_buy_order(self, symbol: str, amount: float):
        """Cria uma ordem de compra a mercado."""
        if self.simulation_mode:
            logging.info(
                f"🔵 [SIMULAÇÃO] Ordem de compra: {amount} {symbol} - Preço simulado: Mercado"
            )
            return {"id": "simulation_buy", "price": 0, "amount": amount, "symbol": symbol}

        try:
            order = self.exchange.create_market_buy_order(symbol, amount)
            logging.info(
                f"\033[92mOrdem de compra executada para {symbol}: {order['price']} USDT\033[0m"
            )
            return order
        except Exception as e:
            logging.error(f"\033[91mErro ao executar compra de {symbol}: {str(e)}\033[0m")
            return None

    def create_market_sell_order(self, symbol: str, amount: float):
        """Cria uma ordem de venda a mercado."""
        if self.simulation_mode:
            logging.info(
                f"🔴 [SIMULAÇÃO] Ordem de venda: {amount} {symbol} - Preço simulado: Mercado"
            )
            return {"id": "simulation_sell", "price": 0, "amount": amount, "symbol": symbol}

        try:
            order = self.exchange.create_market_sell_order(symbol, amount)
            logging.info(
                f"\033[92mOrdem de venda executada para {symbol}: {order['price']} USDT\033[0m"
            )
            return order
        except Exception as e:
            logging.error(f"\033[91mErro ao executar venda de {symbol}: {str(e)}\033[0m")
            return None

    def get_trading_fee(self, symbol: str) -> float:
        """Retorna a taxa de trading para um par específico."""
        return self.trading_fees.get(symbol, 0.001)

    def fetch_ticker(self, symbol: str):
        """Busca informações do ticker para um símbolo."""
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logging.error(f"\033[91mErro ao buscar ticker para {symbol}: {str(e)}\033[0m")
            return None
