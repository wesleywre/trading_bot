"""
WebSocket ultra-simplificado para Binance
Foca em estabilidade máxima.
"""

import asyncio
import json
import logging
import threading
import time
from typing import Dict, List, Callable, Optional
import websockets


class UltraSimpleWebSocket:
    """WebSocket ultra-simplificado e estável para Binance."""
    
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.running = False
        self.connected = False
        self.callbacks: Dict[str, List[Callable]] = {}
        self.last_prices: Dict[str, float] = {}
        
        # Thread para WebSocket
        self.ws_thread: Optional[threading.Thread] = None
        
    def add_price_callback(self, symbol: str, callback: Callable):
        """Adiciona callback para updates de preço."""
        if symbol not in self.callbacks:
            self.callbacks[symbol] = []
        self.callbacks[symbol].append(callback)
        
    def start_monitoring(self):
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
        
    def _start_ws(self):
        """Inicia WebSocket."""
        try:
            asyncio.run(self._ws_loop())
        except Exception as e:
            logging.error(f"❌ Erro WebSocket thread: {e}")
            
    async def _ws_loop(self):
        """Loop WebSocket simplificado."""
        retry_count = 0
        max_retries = 3
        
        while self.running and retry_count < max_retries:
            try:
                retry_count += 1
                
                # Conecta a apenas 1 símbolo por vez para estabilidade
                symbol = self.symbols[0].replace("/", "").lower()
                url = f"wss://stream.testnet.binance.vision/ws/{symbol}@ticker"
                
                logging.info(f"🔄 Conectando WebSocket simples (tentativa {retry_count}): {symbol}")
                
                async with websockets.connect(
                    url, 
                    ping_interval=30,
                    ping_timeout=10
                ) as ws:
                    self.connected = True
                    retry_count = 0  # Reset contador
                    
                    logging.info(f"✅ WebSocket conectado para {symbol.upper()}!")
                    
                    async for message in ws:
                        if not self.running:
                            break
                            
                        try:
                            data = json.loads(message)
                            await self._process_ticker(data)
                        except Exception as e:
                            logging.warning(f"⚠️ Erro processando mensagem: {e}")
                            
            except Exception as e:
                self.connected = False
                logging.error(f"❌ Erro WebSocket: {e}")
                
                if retry_count < max_retries:
                    await asyncio.sleep(10)  # Aguarda antes de tentar novamente
                    
        if retry_count >= max_retries:
            logging.error("🚨 WebSocket falhou após máximo de tentativas")
            
    async def _process_ticker(self, data: dict):
        """Processa dados de ticker."""
        try:
            if 's' in data and 'c' in data:  # symbol e close price
                symbol = data['s']  # Ex: BTCUSDT
                price = float(data['c'])
                
                # Converte para formato padrão (BTC/USDT)
                if symbol.endswith('USDT'):
                    formatted_symbol = f"{symbol[:-4]}/USDT"
                    
                    # Atualiza preço
                    self.last_prices[formatted_symbol] = price
                    
                    # Chama callbacks
                    if formatted_symbol in self.callbacks:
                        for callback in self.callbacks[formatted_symbol]:
                            try:
                                # Chama callback apenas com symbol e price (formato simples)
                                callback(formatted_symbol, price, 0, price, price)  # volume=0, bid=price, ask=price
                            except Exception as e:
                                logging.warning(f"⚠️ Erro callback {formatted_symbol}: {e}")
                                
        except Exception as e:
            logging.warning(f"⚠️ Erro processando ticker: {e}")


# Função de compatibilidade
class SimpleWebSocketMonitor(UltraSimpleWebSocket):
    """Alias para compatibilidade."""
    pass
