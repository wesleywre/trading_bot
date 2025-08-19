"""
Sistema de monitoramento de mercado em tempo real com WebSocket e fallback REST.
Mantém histórico local em SQLite para cálculo de indicadores.
"""

import asyncio
import json
import logging
import sqlite3
import threading
import time
from typing import Callable, Dict, List, Optional

import pandas as pd
import websockets
from colorama import Fore, Style


class MarketDatabase:
    """Gerencia o banco de dados SQLite para histórico de mercado."""

    def __init__(self, db_path: str = "market_data.db"):
        self.db_path = db_path
        self.conn = None
        self._init_database()

    def _init_database(self):
        """Inicializa o banco de dados com as tabelas necessárias."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp REAL NOT NULL,
                price REAL NOT NULL,
                volume REAL NOT NULL,
                bid REAL,
                ask REAL,
                spread REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS order_book (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp REAL NOT NULL,
                side TEXT NOT NULL, -- 'bid' or 'ask'
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ohlcv_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp REAL NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                close_price REAL NOT NULL,
                volume REAL NOT NULL,
                timeframe TEXT NOT NULL DEFAULT '1m',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Índices para performance
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_price_ticks_symbol_time ON price_ticks(symbol, timestamp)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_order_book_symbol_time ON order_book(symbol, timestamp)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time ON ohlcv_data(symbol, timestamp)"
        )

        self.conn.commit()
        logging.info(
            f"{Fore.GREEN}📊 Banco de dados de mercado inicializado: {self.db_path}{Style.RESET_ALL}"
        )

    def insert_price_tick(
        self, symbol: str, price: float, volume: float, bid: float = None, ask: float = None
    ):
        """Insere um tick de preço no banco."""
        timestamp = time.time()
        spread = (ask - bid) if (bid and ask) else None

        self.conn.execute(
            """
            INSERT INTO price_ticks (symbol, timestamp, price, volume, bid, ask, spread)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (symbol, timestamp, price, volume, bid, ask, spread),
        )
        self.conn.commit()

    def insert_order_book_level(self, symbol: str, side: str, price: float, quantity: float):
        """Insere um nível do order book."""
        timestamp = time.time()
        self.conn.execute(
            """
            INSERT INTO order_book (symbol, timestamp, side, price, quantity)
            VALUES (?, ?, ?, ?, ?)
        """,
            (symbol, timestamp, side, price, quantity),
        )
        self.conn.commit()

    def insert_ohlcv(self, symbol: str, ohlcv_data: Dict, timeframe: str = "1m"):
        """Insere dados OHLCV."""
        self.conn.execute(
            """
            INSERT INTO ohlcv_data (symbol, timestamp, open_price, high_price, low_price, close_price, volume, timeframe)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                symbol,
                ohlcv_data["timestamp"],
                ohlcv_data["open"],
                ohlcv_data["high"],
                ohlcv_data["low"],
                ohlcv_data["close"],
                ohlcv_data["volume"],
                timeframe,
            ),
        )
        self.conn.commit()

    def get_recent_prices(self, symbol: str, limit: int = 100) -> pd.DataFrame:
        """Obtém preços recentes para cálculo de indicadores."""
        query = """
            SELECT timestamp, price, volume, bid, ask, spread
            FROM price_ticks 
            WHERE symbol = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """

        df = pd.read_sql_query(query, self.conn, params=(symbol, limit))
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            df = df.sort_values("timestamp").reset_index(drop=True)

        return df

    def get_order_book_snapshot(self, symbol: str, depth: int = 10) -> Dict:
        """Obtém snapshot do order book mais recente."""
        timestamp_cutoff = time.time() - 30  # Dados dos últimos 30 segundos

        # Bids (maiores preços primeiro)
        bids_query = """
            SELECT price, quantity FROM order_book 
            WHERE symbol = ? AND side = 'bid' AND timestamp > ?
            ORDER BY price DESC LIMIT ?
        """

        # Asks (menores preços primeiro)
        asks_query = """
            SELECT price, quantity FROM order_book 
            WHERE symbol = ? AND side = 'ask' AND timestamp > ?
            ORDER BY price ASC LIMIT ?
        """

        bids = self.conn.execute(bids_query, (symbol, timestamp_cutoff, depth)).fetchall()
        asks = self.conn.execute(asks_query, (symbol, timestamp_cutoff, depth)).fetchall()

        return {"bids": bids, "asks": asks, "timestamp": time.time()}

    def cleanup_old_data(self, days_to_keep: int = 7):
        """Remove dados antigos para manter o banco otimizado."""
        cutoff_time = time.time() - (days_to_keep * 24 * 3600)

        self.conn.execute("DELETE FROM price_ticks WHERE timestamp < ?", (cutoff_time,))
        self.conn.execute("DELETE FROM order_book WHERE timestamp < ?", (cutoff_time,))
        self.conn.execute("DELETE FROM ohlcv_data WHERE timestamp < ?", (cutoff_time,))

        self.conn.commit()
        logging.info(f"🧹 Limpeza do banco: dados anteriores a {days_to_keep} dias removidos")


class WebSocketMonitor:
    """Monitor de mercado via WebSocket da Binance com fallback REST - TEMPO REAL OTIMIZADO."""

    def __init__(self, symbols: List[str], exchange_manager, database: MarketDatabase):
        self.symbols = symbols
        self.exchange = exchange_manager
        self.database = database
        self.running = False
        self.websocket_connected = False
        self.callbacks: Dict[str, List[Callable]] = {}
        self.last_prices: Dict[str, float] = {}

        # URLs WebSocket da Binance Testnet - CORRIGIDAS
        self.ws_base_url = "wss://testnet.binance.vision/ws"
        self.ws_stream_url = "wss://testnet.binance.vision/stream"
        self.rest_fallback_interval = 5  # 5 segundos entre requests REST (otimizado)
        
        # Configurações de WebSocket otimizadas
        self.ping_interval = 20  # ping a cada 20s
        self.reconnect_delay = 5  # 5s entre reconexões
        self.connection_attempts = 0
        self.max_connection_attempts = 10
        
        # Métricas de performance
        self.messages_received = 0
        self.last_message_time = 0

        # Thread para fallback REST
        self.rest_thread = None
        self.ws_thread = None

    def add_price_callback(self, symbol: str, callback: Callable):
        """Adiciona callback para ser chamado quando houver update de preço."""
        if symbol not in self.callbacks:
            self.callbacks[symbol] = []
        self.callbacks[symbol].append(callback)

    def start_monitoring(self):
        """Inicia o monitoramento de mercado."""
        self.running = True

        # Inicia WebSocket em thread separada
        self.ws_thread = threading.Thread(target=self._start_websocket_monitor)
        self.ws_thread.start()

        # Inicia fallback REST
        self.rest_thread = threading.Thread(target=self._start_rest_fallback)
        self.rest_thread.start()

        logging.info(
            f"{Fore.GREEN}🚀 Monitoramento de mercado iniciado para {len(self.symbols)} símbolos{Style.RESET_ALL}"
        )

    def stop_monitoring(self):
        """Para o monitoramento."""
        self.running = False
        if self.ws_thread:
            self.ws_thread.join()
        if self.rest_thread:
            self.rest_thread.join()
        logging.info(f"{Fore.YELLOW}⏹️ Monitoramento de mercado parado{Style.RESET_ALL}")

    def _start_websocket_monitor(self):
        """Inicia o monitor WebSocket."""
        try:
            asyncio.run(self._websocket_loop())
        except Exception as e:
            logging.error(f"{Fore.RED}❌ Erro no WebSocket: {e}{Style.RESET_ALL}")
            self.websocket_connected = False

    async def _websocket_loop(self):
        """Loop principal do WebSocket com reconexão inteligente."""
        while self.running and self.connection_attempts < self.max_connection_attempts:
            try:
                self.connection_attempts += 1
                
                # Cria streams para todos os símbolos
                streams = []
                for symbol in self.symbols:
                    base_symbol = symbol.replace("/", "").lower()
                    streams.extend(
                        [
                            f"{base_symbol}@ticker",  # Ticker 24h
                            f"{base_symbol}@depth10@1000ms",  # Order book depth 10 níveis
                            f"{base_symbol}@trade",  # Trades individuais
                            f"{base_symbol}@miniTicker",  # Mini ticker para dados rápidos
                        ]
                    )

                # URL corrigida para Binance Testnet
                stream_names = '/'.join(streams)
                stream_url = f"{self.ws_stream_url}?streams={stream_names}"
                
                logging.info(f"🔄 Tentativa de conexão WebSocket #{self.connection_attempts}")

                async with websockets.connect(
                    stream_url,
                    ping_interval=self.ping_interval,
                    ping_timeout=10,
                    close_timeout=10
                ) as websocket:
                    self.websocket_connected = True
                    self.connection_attempts = 0  # Reset contador em conexão bem-sucedida
                    
                    logging.info(
                        f"{Fore.GREEN}✅ WebSocket conectado para {len(self.symbols)} símbolos "
                        f"(ping: {self.ping_interval}s){Style.RESET_ALL}"
                    )

                    async for message in websocket:
                        if not self.running:
                            break

                        self.messages_received += 1
                        self.last_message_time = time.time()
                        
                        await self._process_websocket_message(json.loads(message))
                        
                        # Log de performance a cada 100 mensagens
                        if self.messages_received % 100 == 0:
                            logging.info(
                                f"📊 WebSocket: {self.messages_received} mensagens recebidas"
                            )

            except websockets.exceptions.ConnectionClosed as e:
                logging.warning(
                    f"{Fore.YELLOW}⚠️ WebSocket desconectado: {e}. "
                    f"Tentando reconectar em {self.reconnect_delay}s...{Style.RESET_ALL}"
                )
                self.websocket_connected = False
                await asyncio.sleep(self.reconnect_delay)
                
            except Exception as e:
                logging.error(
                    f"{Fore.RED}❌ Erro no WebSocket (tentativa {self.connection_attempts}): {e}. "
                    f"Reconectando em {self.reconnect_delay * self.connection_attempts}s...{Style.RESET_ALL}"
                )
                self.websocket_connected = False
                # Backoff exponencial
                await asyncio.sleep(self.reconnect_delay * min(self.connection_attempts, 5))

        if self.connection_attempts >= self.max_connection_attempts:
            logging.error(
                f"{Fore.RED}🚨 Máximo de tentativas de conexão WebSocket atingido. "
                f"Usando apenas REST API.{Style.RESET_ALL}"
            )

    async def _process_websocket_message(self, data: Dict):
        """Processa mensagens do WebSocket com suporte a múltiplos tipos."""
        try:
            stream = data.get("stream", "")
            message_data = data.get("data", {})

            if "@ticker" in stream:
                await self._process_ticker_data(message_data)
            elif "@miniTicker" in stream:
                await self._process_mini_ticker_data(message_data) 
            elif "@depth" in stream:
                await self._process_orderbook_data(message_data)
            elif "@trade" in stream:
                await self._process_trade_data(message_data)

        except Exception as e:
            logging.error(
                f"{Fore.RED}❌ Erro processando mensagem WebSocket: {e}{Style.RESET_ALL}"
            )

    async def _process_ticker_data(self, data: Dict):
        """Processa dados do ticker completo."""
        symbol = data["s"].replace("USDT", "/USDT")  # BTCUSDT -> BTC/USDT
        price = float(data["c"])  # Preço atual
        volume = float(data["v"])  # Volume 24h
        bid = float(data["b"])  # Melhor bid
        ask = float(data["a"])  # Melhor ask

        # Armazena no banco
        self.database.insert_price_tick(symbol, price, volume, bid, ask)

        # Atualiza cache
        self.last_prices[symbol] = price

        # Chama callbacks
        if symbol in self.callbacks:
            for callback in self.callbacks[symbol]:
                callback(symbol, price, volume, bid, ask)

    async def _process_mini_ticker_data(self, data: Dict):
        """Processa dados do mini ticker (mais rápido, menos dados)."""
        symbol = data["s"].replace("USDT", "/USDT")  # BTCUSDT -> BTC/USDT
        price = float(data["c"])  # Preço atual
        volume = float(data["v"])  # Volume 24h
        
        # Atualiza cache rapidamente
        old_price = self.last_prices.get(symbol, 0)
        self.last_prices[symbol] = price
        
        # Log apenas para mudanças significativas (>0.1%)
        if old_price > 0:
            change_pct = abs((price - old_price) / old_price)
            if change_pct >= 0.001:  # 0.1%
                logging.info(
                    f"⚡ {Fore.CYAN}[MINI-TICK] {symbol}: ${price:.2f} "
                    f"Vol: {volume:.0f}{Style.RESET_ALL}"
                )

        # Chama callbacks para mini ticker (sem bid/ask)
        if symbol in self.callbacks:
            for callback in self.callbacks[symbol]:
                callback(symbol, price, volume, 0, 0)  # bid=0, ask=0 para mini ticker

    async def _process_orderbook_data(self, data: Dict):
        """Processa dados do order book."""
        symbol = data["s"].replace("USDT", "/USDT")

        # Processa bids
        for bid in data["bids"]:
            price, quantity = float(bid[0]), float(bid[1])
            if quantity > 0:  # Apenas níveis ativos
                self.database.insert_order_book_level(symbol, "bid", price, quantity)

        # Processa asks
        for ask in data["asks"]:
            price, quantity = float(ask[0]), float(ask[1])
            if quantity > 0:  # Apenas níveis ativos
                self.database.insert_order_book_level(symbol, "ask", price, quantity)

    async def _process_trade_data(self, data: Dict):
        """Processa dados de trades individuais."""
        symbol = data["s"].replace("USDT", "/USDT")
        price = float(data["p"])
        quantity = float(data["q"])

        # Armazena como tick de preço
        self.database.insert_price_tick(symbol, price, quantity)

        # Log de trades significativos (> $1000)
        trade_value = price * quantity
        if trade_value > 1000:
            logging.info(
                f"{Fore.CYAN}💰 Trade grande em {symbol}: "
                f"{quantity:.4f} @ ${price:.2f} = ${trade_value:.2f}{Style.RESET_ALL}"
            )

    def _start_rest_fallback(self):
        """Sistema de fallback via REST API."""
        while self.running:
            try:
                # Se WebSocket está conectado, apenas monitora
                if self.websocket_connected:
                    time.sleep(10)  # Verifica a cada 10 segundos
                    continue

                # WebSocket desconectado, usar REST
                logging.info(
                    f"{Fore.YELLOW}📡 Usando fallback REST (WebSocket desconectado){Style.RESET_ALL}"
                )

                for symbol in self.symbols:
                    try:
                        # Usar exchange manager corretamente
                        if hasattr(self.exchange, 'exchange') and self.exchange.exchange:
                            ticker = self.exchange.exchange.fetch_ticker(symbol)
                        else:
                            logging.warning(f"⚠️ Exchange não disponível para {symbol}")
                            continue
                            
                        if ticker:
                            price = ticker["last"]
                            volume = ticker["baseVolume"] 
                            bid = ticker["bid"]
                            ask = ticker["ask"]

                            # Armazena no banco
                            self.database.insert_price_tick(symbol, price, volume, bid, ask)

                            # Atualiza cache
                            self.last_prices[symbol] = price

                            # Chama callbacks
                            if symbol in self.callbacks:
                                for callback in self.callbacks[symbol]:
                                    callback(symbol, price, volume, bid, ask)

                        # Rate limiting
                        time.sleep(0.1)  # 100ms entre requests

                    except Exception as e:
                        logging.error(
                            f"{Fore.RED}❌ Erro REST para {symbol}: {e}{Style.RESET_ALL}"
                        )

                time.sleep(self.rest_fallback_interval)

            except Exception as e:
                logging.error(f"{Fore.RED}❌ Erro no fallback REST: {e}{Style.RESET_ALL}")
                time.sleep(5)

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Obtém o preço atual de um símbolo."""
        return self.last_prices.get(symbol)

    def get_market_depth(self, symbol: str) -> Dict:
        """Obtém profundidade do mercado."""
        return self.database.get_order_book_snapshot(symbol)

    def get_price_history(self, symbol: str, minutes: int = 60) -> pd.DataFrame:
        """Obtém histórico de preços recente."""
        return self.database.get_recent_prices(
            symbol, limit=minutes * 60
        )  # Assumindo 1 tick/segundo
