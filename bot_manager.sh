#!/bin/bash

# Trading Bot 24/7 Manager
# Script para gerenciar o bot de trading em modo daemon

set -e

# Configurações
BOT_DIR="/home/projects/trading_bot"
BOT_SCRIPT="src/daemon_manager.py"
PID_FILE="/tmp/trading_bot_daemon.pid"
LOG_FILE="$BOT_DIR/daemon.log"
PYTHON_CMD="python3"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para log
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Verifica se o bot está rodando
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Inicia o bot
start_bot() {
    if is_running; then
        warning "Bot já está rodando (PID: $(cat $PID_FILE))"
        return 1
    fi

    log "🚀 Iniciando Trading Bot em modo daemon..."
    
    # Verifica dependências
    if ! command -v $PYTHON_CMD &> /dev/null; then
        error "Python3 não encontrado"
        exit 1
    fi

    # Vai para o diretório do bot
    cd "$BOT_DIR" || {
        error "Diretório do bot não encontrado: $BOT_DIR"
        exit 1
    }

    # Inicia o bot em background
    nohup $PYTHON_CMD "$BOT_SCRIPT" start > "$LOG_FILE" 2>&1 &
    local pid=$!
    
    # Salva PID
    echo $pid > "$PID_FILE"
    
    # Aguarda um pouco e verifica se iniciou corretamente
    sleep 5
    
    if is_running; then
        success "Bot iniciado com sucesso (PID: $pid)"
        success "📊 Logs: tail -f $LOG_FILE"
        success "📊 Logs daemon: tail -f $BOT_DIR/trading_bot_daemon.log"
    else
        error "Falha ao iniciar o bot"
        if [ -f "$LOG_FILE" ]; then
            error "Últimas linhas do log:"
            tail -n 10 "$LOG_FILE"
        fi
        exit 1
    fi
}

# Para o bot
stop_bot() {
    if ! is_running; then
        warning "Bot não está rodando"
        return 0
    fi

    local pid=$(cat "$PID_FILE")
    log "⏹️ Parando Trading Bot (PID: $pid)..."
    
    # Envia SIGTERM para parada graciosa
    kill -TERM "$pid" 2>/dev/null
    
    # Aguarda até 30 segundos para parada graciosa
    local count=0
    while is_running && [ $count -lt 30 ]; do
        sleep 1
        ((count++))
    done
    
    # Se ainda estiver rodando, força a parada
    if is_running; then
        warning "Forçando parada do bot..."
        kill -KILL "$pid" 2>/dev/null
        sleep 2
    fi
    
    # Remove PID file
    rm -f "$PID_FILE"
    
    if is_running; then
        error "Falha ao parar o bot"
        exit 1
    else
        success "Bot parado com sucesso"
    fi
}

# Reinicia o bot
restart_bot() {
    log "🔄 Reiniciando Trading Bot..."
    stop_bot
    sleep 2
    start_bot
}

# Mostra status do bot
status_bot() {
    echo "📊 Status do Trading Bot:"
    echo "========================="
    
    if is_running; then
        local pid=$(cat "$PID_FILE")
        success "Status: RODANDO (PID: $pid)"
        
        # Mostra informações do processo
        if command -v ps &> /dev/null; then
            echo "Processo: $(ps -p $pid -o pid,ppid,etime,pcpu,pmem,cmd --no-headers)"
        fi
        
        # Mostra espaço em disco
        echo "Espaço em disco: $(df -h $BOT_DIR | tail -1 | awk '{print $4}') disponível"
        
        # Mostra últimas linhas do log
        if [ -f "$LOG_FILE" ]; then
            echo ""
            echo "📋 Últimas 5 linhas do log:"
            echo "----------------------------"
            tail -n 5 "$LOG_FILE"
        fi
        
    else
        error "Status: PARADO"
    fi
    
    echo ""
    echo "📂 Arquivos de log:"
    echo "  - Daemon: $BOT_DIR/trading_bot_daemon.log"
    echo "  - Bot: $BOT_DIR/trading_bot.log" 
    echo "  - Sistema: $LOG_FILE"
}

# Mostra logs em tempo real
logs_bot() {
    local log_type=${1:-"daemon"}
    
    case $log_type in
        "daemon"|"d")
            log_file="$BOT_DIR/trading_bot_daemon.log"
            ;;
        "bot"|"b")
            log_file="$BOT_DIR/trading_bot.log"
            ;;
        "system"|"s")
            log_file="$LOG_FILE"
            ;;
        *)
            error "Tipo de log inválido. Use: daemon, bot, system"
            exit 1
            ;;
    esac
    
    if [ ! -f "$log_file" ]; then
        error "Arquivo de log não encontrado: $log_file"
        exit 1
    fi
    
    log "📊 Monitorando $log_file (Ctrl+C para sair)"
    tail -f "$log_file"
}

# Instala como serviço systemd
install_service() {
    local service_file="/etc/systemd/system/trading-bot.service"
    
    log "📦 Instalando como serviço systemd..."
    
    # Verifica se é root
    if [ "$EUID" -ne 0 ]; then
        error "Execute como root para instalar o serviço"
        exit 1
    fi
    
    # Cria arquivo de serviço
    cat > "$service_file" << EOF
[Unit]
Description=Trading Bot 24/7
After=network.target
Wants=network-online.target

[Service]
Type=forking
User=$(logname)
Group=$(logname)
WorkingDirectory=$BOT_DIR
ExecStart=$BOT_DIR/bot_manager.sh start
ExecStop=$BOT_DIR/bot_manager.sh stop
ExecReload=$BOT_DIR/bot_manager.sh restart
PIDFile=$PID_FILE
Restart=on-failure
RestartSec=10
KillMode=process

[Install]
WantedBy=multi-user.target
EOF

    # Recarrega systemd e habilita serviço
    systemctl daemon-reload
    systemctl enable trading-bot.service
    
    success "Serviço instalado com sucesso!"
    success "Use: sudo systemctl start trading-bot"
    success "Para iniciar automaticamente no boot: sudo systemctl enable trading-bot"
}

# Remove serviço systemd
uninstall_service() {
    local service_file="/etc/systemd/system/trading-bot.service"
    
    if [ "$EUID" -ne 0 ]; then
        error "Execute como root para remover o serviço"
        exit 1
    fi
    
    log "🗑️ Removendo serviço systemd..."
    
    # Para e desabilita serviço
    systemctl stop trading-bot.service 2>/dev/null || true
    systemctl disable trading-bot.service 2>/dev/null || true
    
    # Remove arquivo
    rm -f "$service_file"
    systemctl daemon-reload
    
    success "Serviço removido com sucesso!"
}

# Backup da configuração
backup_config() {
    local backup_dir="$BOT_DIR/backups"
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_file="$backup_dir/config_backup_$timestamp.tar.gz"
    
    log "💾 Criando backup da configuração..."
    
    mkdir -p "$backup_dir"
    
    # Cria backup dos arquivos importantes
    tar -czf "$backup_file" -C "$BOT_DIR" \
        config.yaml \
        src/ \
        *.log 2>/dev/null || true
    
    success "Backup criado: $backup_file"
    
    # Limpa backups antigos (mantém últimos 10)
    ls -t "$backup_dir"/config_backup_*.tar.gz 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null || true
}

# Mostra ajuda
show_help() {
    echo "🤖 Trading Bot Manager"
    echo "====================="
    echo ""
    echo "Uso: $0 <comando> [opções]"
    echo ""
    echo "Comandos:"
    echo "  start                 - Inicia o bot em modo daemon"
    echo "  stop                  - Para o bot"
    echo "  restart               - Reinicia o bot"
    echo "  status                - Mostra status do bot"
    echo "  logs [daemon|bot|system] - Mostra logs em tempo real"
    echo "  backup                - Cria backup da configuração"
    echo "  install-service       - Instala como serviço systemd (requer root)"
    echo "  uninstall-service     - Remove serviço systemd (requer root)"
    echo "  help                  - Mostra esta ajuda"
    echo ""
    echo "Exemplos:"
    echo "  $0 start              # Inicia o bot"
    echo "  $0 logs daemon        # Mostra logs do daemon"
    echo "  $0 status             # Verifica se está rodando"
}

# Função principal
main() {
    case "${1:-help}" in
        start)
            start_bot
            ;;
        stop)
            stop_bot
            ;;
        restart)
            restart_bot
            ;;
        status)
            status_bot
            ;;
        logs)
            logs_bot "$2"
            ;;
        backup)
            backup_config
            ;;
        install-service)
            install_service
            ;;
        uninstall-service)
            uninstall_service
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            error "Comando desconhecido: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Executa função principal
main "$@"
