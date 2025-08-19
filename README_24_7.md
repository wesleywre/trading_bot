# 🤖 Trading Bot 24/7

Sistema automatizado de trading de criptomoedas com execução contínua, auto-recuperação e monitoramento avançado.

## ✨ Características

### 🎯 **Trading Multi-Crypto**
- **5 criptomoedas simultâneas**: BTC, ETH, BNB, SOL, ADA
- **Estratégias especializadas**: Large-cap e Mid-cap
- **Análise técnica avançada**: RSI, EMA, Volume, Breakouts

### 🛡️ **Gestão de Risco Ultra-Conservadora**
- **Risco por trade**: Máximo 1% do capital
- **Posição máxima**: 10% do portfólio por crypto
- **Stop Loss automático**: 2.5% (large-cap) / 3.5% (mid-cap)
- **Take Profit inteligente**: 5.0% / 8.0%
- **Reserva de segurança**: 15% sempre disponível

### 🚀 **Execução 24/7**
- **Auto-recuperação** de falhas de conexão
- **Reconexão automática** com backoff exponencial
- **Monitor de saúde** em tempo real
- **Logs rotativos** e backup automático
- **Reinicialização inteligente** em caso de erros

### 📊 **Monitoramento Avançado**
- **Logs coloridos** e organizados por categoria
- **Resumo de conta** em tempo real
- **Performance tracking** por crypto
- **Alertas de sistema** e notificações
- **Métricas de health** (CPU, RAM, conectividade)

## 📋 Pré-requisitos

- **Sistema**: Linux (Ubuntu/Debian recomendado)
- **Python**: 3.7+ 
- **Memória**: 512MB RAM mínimo
- **Espaço**: 2GB livre para logs e dados
- **Internet**: Conexão estável

## 🚀 Instalação Rápida

### 1. **Instalação Automática**
```bash
cd /home/projects/trading_bot
chmod +x install_24_7.sh
./install_24_7.sh
```

### 2. **Configuração da API**
Edite o arquivo `config.yaml` com suas credenciais:
```yaml
exchange:
  api_key: "SUA_API_KEY_AQUI"
  api_secret: "SUA_SECRET_KEY_AQUI"
  testnet: true  # Mude para false em produção
```

### 3. **Iniciar o Bot**
```bash
./bot_manager.sh start
```

## 🎛️ Comandos Principais

### **Gerenciamento Básico**
```bash
./bot_manager.sh start          # Inicia o bot
./bot_manager.sh stop           # Para o bot
./bot_manager.sh restart        # Reinicia o bot
./bot_manager.sh status         # Mostra status completo
```

### **Monitoramento**
```bash
./bot_manager.sh logs daemon    # Logs do sistema daemon
./bot_manager.sh logs bot       # Logs das operações de trading
./monitor.sh                    # Monitor de saúde rápido
```

### **Manutenção**
```bash
./bot_manager.sh backup         # Backup da configuração
./healthcheck.sh                # Verificação manual de saúde
```

### **Serviço Systemd (Opcional)**
```bash
sudo ./bot_manager.sh install-service      # Instala como serviço
sudo systemctl start trading-bot           # Inicia via systemd
sudo systemctl enable trading-bot          # Auto-start no boot
```

## 📊 Estrutura dos Logs

### **trading_bot_daemon.log**
```
2025-08-01 10:51:42,030 - INFO - [DAEMON] 🚀 Trading Bot Daemon iniciado
2025-08-01 10:51:55,014 - INFO - [DAEMON] 💰 Balanço inicial: $198.27 USDT
2025-08-01 10:52:01,364 - INFO - [DAEMON] 📈 [ETH/USDT] COMPRA: $3595.49 (0.005510)
```

### **healthcheck.log**
```
[2025-08-01 11:00:01] Verificando saúde do bot...
[2025-08-01 11:00:01] Bot está funcionando normalmente
[2025-08-01 11:05:01] Verificando saúde do bot...
```

## 🛠️ Configurações Avançadas

### **Perfis de Risco**
```yaml
risk_profiles:
  conservative:    # Risco muito baixo
    max_position_size: 0.05      # 5% por posição
    risk_per_trade: 0.005        # 0.5% por trade
  
  moderate:        # Risco equilibrado (padrão)
    max_position_size: 0.10      # 10% por posição  
    risk_per_trade: 0.01         # 1% por trade
  
  aggressive:      # Risco alto
    max_position_size: 0.20      # 20% por posição
    risk_per_trade: 0.02         # 2% por trade
```

### **Estratégias Disponíveis**

#### **Large-Cap (BTC, ETH)**
- `trend_following`: Segue tendências de longo prazo
- `mean_reversion`: Reversão à média com RSI

#### **Mid-Cap (BNB, SOL, ADA)**  
- `breakout`: Trading de rompimentos
- `momentum_volume`: Momentum com confirmação de volume
- `liquidity_scalping`: Scalping em alta liquidez

### **Configurações de Sistema**
```yaml
daemon:
  auto_restart: true           # Auto-reinicialização
  max_restarts: 5             # Máximo de reinicializações
  health_check_interval: 300  # Verificação a cada 5min
  reconnect_delay: 30         # Delay entre reconexões
  
logging:
  level: INFO                 # Nível de log
  max_size: 50MB             # Tamanho máximo por arquivo
  backup_count: 10           # Quantidade de backups
```

## 📈 Monitoramento da Performance

### **Resumo da Conta**
```
📊 RESUMO COMPLETO DA CONTA 📊
============================================================
💰 Saldo total: 178.49 USDT
🛡️ GESTÃO DE RISCO:
   Risco do portfólio: 0.33%
   Posições ativas: 1
   P&L diário: +12.50 USDT (+7.02%)
   Win Rate: 75.0%
   Trades hoje: 4

📈 [ETH/USDT] Performance:
   Trades realizados: 3
   Lucro/Prejuízo: +8.75 USDT (+4.93%)
   Em posição: 🟢 SIM
```

### **Status do Sistema**
```bash
./bot_manager.sh status

📊 Status do Trading Bot:
=========================
✅ Status: RODANDO (PID: 12345)
Processo: 12345 1234 02:15:30 2.5 1.2 python3 daemon_manager.py
Espaço em disco: 15.2G disponível

📋 Últimas 5 linhas do log:
----------------------------
2025-08-01 11:15:40,366 - INFO - ⏸️ ETH/USDT: MANTER POSIÇÃO
2025-08-01 11:16:42,456 - INFO - 📊 [PERFORMANCE] Win Rate: 80.0%
```

## 🔧 Solução de Problemas

### **Bot não inicia**
```bash
# Verifica logs de erro
tail -f daemon.log

# Testa configuração
python3 src/daemon_manager.py status

# Verifica dependências
./install_24_7.sh
```

### **Perda de conexão**
- **Auto-reconexão**: O sistema tenta reconectar automaticamente
- **Backoff exponencial**: Delay crescente entre tentativas
- **Máximo 10 tentativas** antes de parar

### **Alto uso de memória**
```bash
# Verifica uso de recursos
./monitor.sh

# Reinicia se necessário
./bot_manager.sh restart
```

### **Logs muito grandes**
- **Rotação automática**: Logs rodam automaticamente (10MB)
- **Limpeza programada**: Via logrotate (/etc/logrotate.d/trading-bot)
- **Backup limitado**: Mantém últimos 30 dias

## 📁 Estrutura de Arquivos

```
trading_bot/
├── src/                          # Código fonte
│   ├── daemon_manager.py         # Sistema daemon 24/7
│   ├── trader.py                 # Trading engine
│   ├── exchange_manager.py       # Gerenciamento da exchange
│   ├── risk_manager.py           # Gestão de risco
│   ├── account_tracker.py        # Tracking de conta
│   └── strategies/               # Estratégias de trading
├── config.yaml                   # Configuração principal
├── bot_manager.sh                # Script de gerenciamento
├── install_24_7.sh              # Instalação automática
├── monitor.sh                    # Monitor de saúde
├── healthcheck.sh                # Verificação automática
├── logs/                         # Diretório de logs
├── backups/                      # Backups automáticos
└── data/                         # Dados de mercado
```

## 🔒 Segurança

### **API Keys**
- **Testnet recomendado** para testes
- **Permissões mínimas**: Apenas trading (não saque)
- **Rotação regular** das chaves
- **Backup seguro** das configurações

### **Monitoramento**
- **Alertas automáticos** para falhas
- **Logs de segurança** para todas as operações
- **Backup diário** das configurações
- **Health checks** a cada 5 minutos

## 📞 Suporte

### **Logs de Debug**
```bash
# Ativa modo debug
export BOT_LOG_LEVEL=DEBUG
./bot_manager.sh restart

# Monitora logs em tempo real
./bot_manager.sh logs daemon
```

### **Reset Completo**
```bash
./bot_manager.sh stop
rm -f /tmp/trading_bot_daemon.pid
./bot_manager.sh start
```

---

## 🎯 **Sistema Pronto para Produção 24/7!**

✅ **Auto-recuperação** de falhas  
✅ **Reconexão automática** com exchanges  
✅ **Gestão de risco conservadora**  
✅ **Monitoramento contínuo**  
✅ **Logs organizados** e rotativos  
✅ **Backup automático**  
✅ **Health checks** regulares  

**Inicie agora**: `./bot_manager.sh start` 🚀
