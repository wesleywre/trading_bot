#!/bin/bash

# Trading Bot 24/7 - Script de Instalação
# Configura o sistema para execução contínua 24/7

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configurações
BOT_DIR="/home/projects/trading_bot"
SERVICE_USER=$(logname 2>/dev/null || echo "root")

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Função para verificar dependências
check_dependencies() {
    log "🔍 Verificando dependências..."
    
    local missing_deps=()
    
    # Verifica Python3
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi
    
    # Verifica pip
    if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
        missing_deps+=("python3-pip")
    fi
    
    # Verifica systemctl (para serviços)
    if ! command -v systemctl &> /dev/null; then
        warning "systemctl não encontrado - serviços systemd não estarão disponíveis"
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        error "Dependências ausentes: ${missing_deps[*]}"
        log "Install them with: sudo apt update && sudo apt install ${missing_deps[*]}"
        exit 1
    fi
    
    success "Todas as dependências encontradas"
}

# Instala dependências Python
install_python_deps() {
    log "📦 Instalando dependências Python..."
    
    cd "$BOT_DIR"
    
    # Lista de dependências essenciais
    local deps=(
        "psutil>=5.8.0"
        "pandas>=1.5.0"
        "numpy>=1.21.0"
        "requests>=2.25.0"
        "websocket-client>=1.0.0"
        "colorama>=0.4.4"
        "python-binance>=1.0.0"
        "python-dotenv>=0.19.0"
        "pyyaml>=6.0"
    )
    
    # Instala cada dependência
    for dep in "${deps[@]}"; do
        log "Instalando $dep..."
        pip3 install "$dep" --user --upgrade
    done
    
    success "Dependências Python instaladas"
}

# Cria diretórios necessários
create_directories() {
    log "📁 Criando diretórios necessários..."
    
    local dirs=(
        "$BOT_DIR/logs"
        "$BOT_DIR/backups"
        "$BOT_DIR/data"
        "/tmp/trading_bot"
    )
    
    for dir in "${dirs[@]}"; do
        mkdir -p "$dir"
        log "Criado: $dir"
    done
    
    success "Diretórios criados"
}

# Configura logrotate
setup_logrotate() {
    if [ "$EUID" -ne 0 ]; then
        warning "Pulando configuração do logrotate (requer root)"
        return
    fi
    
    log "📋 Configurando rotação de logs..."
    
    cat > /etc/logrotate.d/trading-bot << EOF
$BOT_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
    create 644 $SERVICE_USER $SERVICE_USER
}
EOF
    
    success "Logrotate configurado"
}

# Cria script de monitoramento
create_monitor_script() {
    log "📊 Criando script de monitoramento..."
    
    cat > "$BOT_DIR/monitor.sh" << 'EOF'
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
EOF

    chmod +x "$BOT_DIR/monitor.sh"
    success "Script de monitoramento criado: $BOT_DIR/monitor.sh"
}

# Configura crontab para verificação periódica
setup_crontab() {
    log "⏰ Configurando verificação automática via crontab..."
    
    # Script de verificação
    cat > "$BOT_DIR/healthcheck.sh" << 'EOF'
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
EOF

    chmod +x "$BOT_DIR/healthcheck.sh"
    
    # Adiciona ao crontab (verifica a cada 5 minutos)
    (crontab -l 2>/dev/null; echo "*/5 * * * * $BOT_DIR/healthcheck.sh") | crontab -
    
    success "Healthcheck configurado para executar a cada 5 minutos"
}

# Configura variáveis de ambiente
setup_environment() {
    log "🔧 Configurando variáveis de ambiente..."
    
    # Cria arquivo de ambiente
    cat > "$BOT_DIR/.env" << EOF
# Trading Bot Environment Configuration
PYTHONPATH=$BOT_DIR/src
BOT_LOG_LEVEL=INFO
BOT_LOG_FILE=$BOT_DIR/trading_bot.log
BOT_CONFIG_FILE=$BOT_DIR/config.yaml

# Configurações de sistema
BOT_AUTO_RESTART=true
BOT_MAX_RESTARTS=5
BOT_HEALTH_CHECK_INTERVAL=300
BOT_RECONNECT_DELAY=30
EOF

    success "Arquivo de ambiente criado: $BOT_DIR/.env"
}

# Testa a instalação
test_installation() {
    log "🧪 Testando instalação..."
    
    cd "$BOT_DIR"
    
    # Testa importação dos módulos
    if python3 -c "
import sys
sys.path.append('src')
try:
    import daemon_manager
    import trader
    import exchange_manager
    print('✅ Módulos importados com sucesso')
except ImportError as e:
    print(f'❌ Erro de importação: {e}')
    sys.exit(1)
"; then
        success "Teste de módulos: OK"
    else
        error "Teste de módulos: FALHOU"
        exit 1
    fi
    
    # Testa script de gerenciamento
    if ./bot_manager.sh help > /dev/null 2>&1; then
        success "Teste do manager: OK"
    else
        error "Teste do manager: FALHOU"
        exit 1
    fi
    
    # Verifica configuração
    if [ -f "config.yaml" ]; then
        success "Arquivo de configuração: OK"
    else
        warning "Arquivo de configuração não encontrado"
        log "Certifique-se de ter um config.yaml válido antes de iniciar"
    fi
}

# Mostra informações finais
show_final_info() {
    echo ""
    echo "🎉 Trading Bot configurado para execução 24/7!"
    echo "================================================="
    echo ""
    echo "📋 Comandos disponíveis:"
    echo "  $BOT_DIR/bot_manager.sh start     - Iniciar bot"
    echo "  $BOT_DIR/bot_manager.sh stop      - Parar bot"
    echo "  $BOT_DIR/bot_manager.sh status    - Ver status"
    echo "  $BOT_DIR/bot_manager.sh logs      - Ver logs"
    echo "  $BOT_DIR/monitor.sh               - Monitor de saúde"
    echo ""
    echo "📂 Arquivos importantes:"
    echo "  Config: $BOT_DIR/config.yaml"
    echo "  Logs: $BOT_DIR/trading_bot_daemon.log"
    echo "  Health: $BOT_DIR/healthcheck.log"
    echo ""
    echo "🔧 Próximos passos:"
    echo "  1. Verifique suas configurações de API em config.yaml"
    echo "  2. Execute: $BOT_DIR/bot_manager.sh start"
    echo "  3. Monitor com: $BOT_DIR/bot_manager.sh status"
    echo ""
    if command -v systemctl &> /dev/null; then
        echo "⚙️ Para instalar como serviço do sistema:"
        echo "  sudo $BOT_DIR/bot_manager.sh install-service"
        echo ""
    fi
    echo "✅ Sistema pronto para operar 24/7!"
}

# Função principal
main() {
    echo "🤖 Trading Bot 24/7 - Instalação"
    echo "================================="
    echo ""
    
    check_dependencies
    install_python_deps
    create_directories
    setup_logrotate
    create_monitor_script
    setup_crontab
    setup_environment
    test_installation
    
    success "Instalação concluída com sucesso!"
    show_final_info
}

# Executa se chamado diretamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
