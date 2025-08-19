#!/bin/bash

BOT_DIR="/home/projects/trading_bot"
PID_FILE="/tmp/trading_bot_daemon.pid"
LOG_FILE="$BOT_DIR/healthcheck.log"

echo "[$(date)] Verificando saúde do bot..." >> "$LOG_FILE"

# Verifica se está rodando
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "[$(date)] Bot não está rodando, tentando reiniciar..." >> "$LOG_FILE"
        cd "$BOT_DIR"
        ./bot_manager.sh start >> "$LOG_FILE" 2>&1
    else
        echo "[$(date)] Bot está funcionando normalmente" >> "$LOG_FILE"
    fi
else
    echo "[$(date)] PID file não encontrado, tentando iniciar bot..." >> "$LOG_FILE"
    cd "$BOT_DIR"
    ./bot_manager.sh start >> "$LOG_FILE" 2>&1
fi

# Limita o tamanho do log
tail -n 100 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
