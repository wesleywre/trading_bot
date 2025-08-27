"""
WebSocket ultra-simplificado para Binance
Foca em estabilidade máxima.
"""

import asyncio
import json
import logging
import threading
import time
from typing import Callable, Dict, List, Optional

import websockets


class UltraSimpleWebSocket:
    """WebSocket ultra-simplificado e estável para Binance."""

    def __init__(self, symbols: List[str]) -> None:
        self.symbols = symbols
        self.running = False
        self.connected = False
        self.callbacks: Dict[str, List[Callable]] = {}
        self.last_prices: Dict[str, float] = {}
        self.market_depth_data: Dict[str, Dict] = {}

        # Thread para WebSocket
        self.ws_thread: Optional[threading.Thread] = None

    def add_price_callback(self, symbol: str, callback: Callable) -> None:
        """Adiciona callback para updates de preço."""
        if symbol not in self.callbacks:
            self.callbacks[symbol] = []
        self.callbacks[symbol].append(callback)

    def start_monitoring(self) -> None:
        """Inicia monitoramento WebSocket."""
        if self.running:
            return

        self.running = True
        self.ws_thread = threading.Thread(target=self._start_ws, daemon=True)
        self.ws_thread.start()

        logging.info(f"🚀 Ultra WebSocket iniciado para {len(self.symbols)} símbolos")

    def stop_monitoring(self):
        """Para monitoramento."""
        self.running = False
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5)

    def is_connected(self) -> bool:
        """Retorna se está conectado."""
        return self.connected

    def get_last_price(self, symbol: str) -> Optional[float]:
        """Retorna último preço conhecido."""
        return self.last_prices.get(symbol)

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Método de compatibilidade - retorna último preço conhecido."""
        return self.last_prices.get(symbol)

    def get_market_depth(self, symbol: str) -> Dict:
        """Retorna dados do order book (simulado para compatibilidade)."""
        price = self.last_prices.get(symbol, 0)
        if price == 0:
            return {"bids": [], "asks": [], "timestamp": time.time()}

        # Simula order book básico
        bid_price = price * 0.999  # 0.1% abaixo
        ask_price = price * 1.001  # 0.1% acima

        return {
            "bids": [[bid_price, 1.0]],  # [preço, quantidade]
            "asks": [[ask_price, 1.0]],
            "timestamp": time.time(),
        }

    def _start_ws(self):
        """Inicia WebSocket."""
        try:
            asyncio.run(self._ws_loop())
        except Exception as e:
            logging.error(f"❌ Erro WebSocket thread: {e}")

    async def _ws_loop(self):
        """Loop WebSocket para múltiplos símbolos."""
        retry_count = 0
        max_retries = 3

        while self.running and retry_count < max_retries:
            try:
                retry_count += 1

                # Cria streams para TODOS os símbolos
                streams = []
                for symbol in self.symbols:
                    base_symbol = symbol.replace("/", "").lower()
                    streams.append(f"{base_symbol}@ticker")

                # URL para múltiplos streams
                stream_names = "/".join(streams)
                url = f"wss://stream.testnet.binance.vision/stream?streams={stream_names}"

                logging.info(
                    f"🔄 Conectando WebSocket para {len(self.symbols)} símbolos (tentativa {retry_count})"
                )
                logging.info(f"📡 Símbolos: {', '.join(self.symbols)}")

                async with websockets.connect(url, ping_interval=30, ping_timeout=10) as ws:
                    self.connected = True
                    retry_count = 0  # Reset contador

                    logging.info(f"✅ WebSocket conectado para {len(self.symbols)} símbolos!")

                    async for message in ws:
                        if not self.running:
                            break

                        try:
                            data = json.loads(message)
                            await self._process_message(data)
                        except Exception as e:
                            logging.warning(f"⚠️ Erro processando mensagem: {e}")

            except Exception as e:
                self.connected = False
                logging.error(f"❌ Erro WebSocket: {e}")

                if retry_count < max_retries:
                    await asyncio.sleep(10)  # Aguarda antes de tentar novamente

        if retry_count >= max_retries:
            logging.error("🚨 WebSocket falhou após máximo de tentativas")

    async def _process_message(self, data: dict):
        """Processa mensagem do WebSocket (pode ser stream ou ticker direto)."""
        try:
            # Verifica se é uma mensagem de stream (múltiplos símbolos)
            if "stream" in data and "data" in data:
                await self._process_ticker(data["data"])
            else:
                # Mensagem direta de ticker (símbolo único)
                await self._process_ticker(data)
        except Exception as e:
            logging.warning(f"⚠️ Erro processando mensagem: {e}")

    async def _process_ticker(self, data: dict):
        """Processa dados de ticker."""
        try:
            if "s" in data and "c" in data:  # symbol e close price
                symbol = data["s"]  # Ex: BTCUSDT
                price = float(data["c"])
                volume = float(data.get("v", 0))  # Volume 24h

                # Converte para formato padrão (BTC/USDT)
                if symbol.endswith("USDT"):
                    formatted_symbol = f"{symbol[:-4]}/USDT"

                    # Atualiza preço
                    self.last_prices[formatted_symbol] = price

                    # Log apenas para mudanças significativas
                    logging.info(f"📡 {formatted_symbol}: ${price:.2f}")

                    # Chama callbacks
                    if formatted_symbol in self.callbacks:
                        for callback in self.callbacks[formatted_symbol]:
                            try:
                                # Chama callback com dados completos
                                callback(formatted_symbol, price, volume, price, price)
                            except Exception as e:
                                logging.warning(f"⚠️ Erro callback {formatted_symbol}: {e}")

        except Exception as e:
            logging.warning(f"⚠️ Erro processando ticker: {e}")


# Função de compatibilidade
class SimpleWebSocketMonitor(UltraSimpleWebSocket):
    """Alias para compatibilidade."""

    pass
