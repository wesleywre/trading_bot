#!/bin/bash

# Monitor de saúde do Trading Bot
BOT_DIR="/home/projects/trading_bot"
PID_FILE="/tmp/trading_bot_daemon.pid"

# Verifica se o bot está rodando
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "✅ Bot está rodando (PID: $PID)"
        
        # Mostra uso de recursos
        ps -p "$PID" -o pid,ppid,etime,pcpu,pmem,cmd --no-headers
        
        # Verifica logs recentes
        echo ""
        echo "📋 Últimas atividades:"
        tail -n 5 "$BOT_DIR/trading_bot_daemon.log" 2>/dev/null || echo "Log não encontrado"
        
    else
        echo "❌ Bot não está rodando (PID file órfão)"
        rm -f "$PID_FILE"
        exit 1
    fi
else
    echo "❌ Bot não está rodando"
    exit 1
fi
