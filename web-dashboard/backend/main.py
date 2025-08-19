"""
Trading Bot Web Dashboard - Backend API
FastAPI server para servir dados do trading bot em tempo real.
"""

import asyncio
import json
import logging
import os
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import psutil
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Adiciona o diretório src ao path para importar os módulos do bot
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

try:
    from config_manager import ConfigManager
    from dotenv import load_dotenv
except ImportError:
    print("⚠️ Módulos do bot não encontrados. Certifique-se de que o bot está configurado.")


# Carrega variáveis de ambiente
load_dotenv()

# Configuração da API
app = FastAPI(
    title="Trading Bot Dashboard API",
    description="API para monitoramento e controle do Trading Bot 24/7",
    version="1.0.0"
)

# CORS para desenvolvimento
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Armazena conexões WebSocket ativas
active_connections: List[WebSocket] = []

# Cache de dados
data_cache = {
    "bot_status": {},
    "portfolio": {},
    "trading_pairs": {},
    "logs": [],
    "performance": {}
}


class BotStatus(BaseModel):
    """Status do bot."""
    is_running: bool
    pid: Optional[int]
    uptime: str
    memory_usage: float
    cpu_usage: float
    websocket_connected: bool
    last_update: datetime


class TradingPair(BaseModel):
    """Informações de um par de trading."""
    symbol: str
    current_price: float
    change_24h: float
    volume_24h: float
    last_signal: str
    strategy: str
    pnl: float
    status: str


class Portfolio(BaseModel):
    """Portfolio do usuário."""
    total_balance: float
    available_balance: float
    in_positions: float
    total_pnl: float
    daily_pnl: float
    positions: List[Dict]


@app.get("/")
async def root():
    """Endpoint raiz."""
    return {"message": "Trading Bot Dashboard API", "status": "running"}


@app.get("/api/bot/status", response_model=BotStatus)
async def get_bot_status():
    """Retorna o status atual do bot."""
    try:
        # Busca PID do processo
        bot_pid = None
        is_running = False
        uptime = "0:00:00"
        memory_usage = 0.0
        cpu_usage = 0.0
        
        # Procura processo do bot
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] == 'python3' and proc.info['cmdline']:
                    if any('daemon_manager.py' in cmd for cmd in proc.info['cmdline']):
                        bot_pid = proc.info['pid']
                        is_running = True
                        
                        # Informações do processo
                        process = psutil.Process(bot_pid)
                        memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                        cpu_usage = process.cpu_percent()
                        
                        # Uptime
                        create_time = datetime.fromtimestamp(process.create_time())
                        uptime_delta = datetime.now() - create_time
                        uptime = str(uptime_delta).split('.')[0]  # Remove microsegundos
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Verifica conexão WebSocket (lê do log)
        websocket_connected = await check_websocket_status()
        
        return BotStatus(
            is_running=is_running,
            pid=bot_pid,
            uptime=uptime,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
            websocket_connected=websocket_connected,
            last_update=datetime.now()
        )
        
    except Exception as e:
        logging.error(f"Erro ao obter status do bot: {e}")
        return BotStatus(
            is_running=False,
            pid=None,
            uptime="N/A",
            memory_usage=0.0,
            cpu_usage=0.0,
            websocket_connected=False,
            last_update=datetime.now()
        )


async def check_websocket_status() -> bool:
    """Verifica se o WebSocket está conectado baseado nos logs."""
    try:
        log_file = Path(__file__).parent.parent.parent / "trading_bot_daemon.log"
        if log_file.exists():
            # Lê as últimas 50 linhas
            with open(log_file, 'r') as f:
                lines = f.readlines()[-50:]
            
            # Procura por mensagens de conexão WebSocket recentes (últimos 5 minutos)
            for line in reversed(lines):
                if "WebSocket conectado" in line:
                    return True
                elif "Erro WebSocket" in line or "WebSocket desconectado" in line:
                    return False
                    
        return False
    except Exception:
        return False


@app.get("/api/trading/pairs", response_model=List[TradingPair])
async def get_trading_pairs():
    """Retorna informações de todos os pares de trading."""
    try:
        config = ConfigManager("../config.yaml")
        config.load_config()
        
        pairs = []
        for pair_config in config.get_trading_pairs():
            symbol = pair_config['symbol']
            
            # Busca informações do log para este par
            pair_info = await get_pair_info_from_logs(symbol)
            
            pairs.append(TradingPair(
                symbol=symbol,
                current_price=pair_info.get('price', 0.0),
                change_24h=pair_info.get('change_24h', 0.0),
                volume_24h=pair_info.get('volume_24h', 0.0),
                last_signal=pair_info.get('signal', 'NEUTRO'),
                strategy=pair_config.get('strategy', 'unknown'),
                pnl=pair_info.get('pnl', 0.0),
                status=pair_info.get('status', 'AGUARDAR')
            ))
            
        return pairs
        
    except Exception as e:
        logging.error(f"Erro ao obter pares de trading: {e}")
        return []


async def get_pair_info_from_logs(symbol: str) -> Dict:
    """Extrai informações de um par dos logs."""
    try:
        log_file = Path(__file__).parent.parent.parent / "trading_bot_daemon.log"
        if not log_file.exists():
            return {}
            
        # Lê últimas 200 linhas
        with open(log_file, 'r') as f:
            lines = f.readlines()[-200:]
        
        pair_info = {}
        
        # Busca informações mais recentes do par
        for line in reversed(lines):
            if symbol in line:
                if "💰 [PREÇO]" in line:
                    # Extrai preço
                    try:
                        price_part = line.split("💰 [PREÇO]")[1].split("$")[1]
                        price = float(price_part.split()[0])
                        pair_info['price'] = price
                    except:
                        pass
                        
                elif "📊 Sinais:" in line:
                    # Extrai sinal
                    if "🟢 COMPRA" in line:
                        pair_info['signal'] = 'COMPRA'
                    elif "🔴 VENDA" in line:
                        pair_info['signal'] = 'VENDA'
                    else:
                        pair_info['signal'] = 'NEUTRO'
                        
                elif "AGUARDAR OPORTUNIDADE" in line:
                    pair_info['status'] = 'AGUARDAR'
                elif "COMPRA EXECUTADA" in line:
                    pair_info['status'] = 'COMPRADO'
                elif "VENDA EXECUTADA" in line:
                    pair_info['status'] = 'VENDIDO'
        
        return pair_info
        
    except Exception:
        return {}


@app.get("/api/portfolio", response_model=Portfolio)
async def get_portfolio():
    """Retorna informações do portfolio."""
    try:
        # Para modo simulação, retorna dados mockados baseados nos logs
        # Em produção, isso viria da exchange via API
        
        return Portfolio(
            total_balance=10000.0,  # Saldo inicial de simulação
            available_balance=9500.0,
            in_positions=500.0,
            total_pnl=0.0,
            daily_pnl=0.0,
            positions=[]
        )
        
    except Exception as e:
        logging.error(f"Erro ao obter portfolio: {e}")
        return Portfolio(
            total_balance=0.0,
            available_balance=0.0,
            in_positions=0.0,
            total_pnl=0.0,
            daily_pnl=0.0,
            positions=[]
        )


@app.get("/api/logs")
async def get_recent_logs(limit: int = 50):
    """Retorna logs recentes do bot."""
    try:
        log_file = Path(__file__).parent.parent.parent / "trading_bot_daemon.log"
        if not log_file.exists():
            return {"logs": []}
            
        with open(log_file, 'r') as f:
            lines = f.readlines()[-limit:]
            
        logs = []
        for line in lines:
            if line.strip():
                # Parseia linha do log
                parts = line.strip().split(' - ', 3)
                if len(parts) >= 4:
                    timestamp = parts[0]
                    level = parts[1]
                    source = parts[2]
                    message = parts[3]
                    
                    logs.append({
                        "timestamp": timestamp,
                        "level": level,
                        "source": source,
                        "message": message
                    })
        
        return {"logs": logs}
        
    except Exception as e:
        logging.error(f"Erro ao obter logs: {e}")
        return {"logs": []}


@app.post("/api/bot/start")
async def start_bot():
    """Inicia o bot."""
    try:
        import subprocess
        result = subprocess.run(
            ["./bot_manager.sh", "start"],
            cwd=str(Path(__file__).parent.parent.parent),
            capture_output=True,
            text=True
        )
        
        return {
            "success": result.returncode == 0,
            "message": result.stdout,
            "error": result.stderr
        }
    except Exception as e:
        return {
            "success": False,
            "message": "",
            "error": str(e)
        }


@app.post("/api/bot/stop")
async def stop_bot():
    """Para o bot."""
    try:
        import subprocess
        result = subprocess.run(
            ["./bot_manager.sh", "stop"],
            cwd=str(Path(__file__).parent.parent.parent),
            capture_output=True,
            text=True
        )
        
        return {
            "success": result.returncode == 0,
            "message": result.stdout,
            "error": result.stderr
        }
    except Exception as e:
        return {
            "success": False,
            "message": "",
            "error": str(e)
        }


@app.post("/api/bot/restart")
async def restart_bot():
    """Reinicia o bot."""
    try:
        import subprocess
        result = subprocess.run(
            ["./bot_manager.sh", "restart"],
            cwd=str(Path(__file__).parent.parent.parent),
            capture_output=True,
            text=True
        )
        
        return {
            "success": result.returncode == 0,
            "message": result.stdout,
            "error": result.stderr
        }
    except Exception as e:
        return {
            "success": False,
            "message": "",
            "error": str(e)
        }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para dados em tempo real."""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Envia atualizações a cada 5 segundos
            await asyncio.sleep(5)
            
            # Coleta dados atualizados
            status = await get_bot_status()
            pairs = await get_trading_pairs()
            
            data = {
                "type": "update",
                "timestamp": datetime.now().isoformat(),
                "status": status.dict(),
                "pairs": [pair.dict() for pair in pairs]
            }
            
            await websocket.send_text(json.dumps(data, default=str))
            
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        logging.error(f"Erro no WebSocket: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


if __name__ == "__main__":
    print("🚀 Iniciando Trading Bot Dashboard API...")
    print("📊 Dashboard disponível em: http://localhost:8000")
    print("🔌 WebSocket endpoint: ws://localhost:8000/ws")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
