# 📋 GitIgnore - Trading Bot

## 🎯 Arquivos e Pastas Ignorados

### 🐍 Python
- `__pycache__/` - Cache de bytecode Python
- `*.pyc`, `*.pyo` - Arquivos compilados
- `build/`, `dist/` - Arquivos de build
- `.eggs/`, `*.egg-info/` - Packages Python

### 🌍 Ambientes Virtuais
- `.venv/`, `venv/` - Ambientes virtuais Python
- `.env` - Variáveis de ambiente (SENSÍVEL!)

### 💾 Dados e Logs
- `*.log` - Logs do sistema
- `logs/` - Pasta de logs
- `*.db`, `*.sqlite` - Bancos de dados
- `data/` - Dados de mercado (podem ser grandes)
- `backups/` - Backups automáticos

### 🖥️ IDEs e Editores
- `.vscode/`, `.idea/` - Configurações de IDEs
- `*.swp`, `*.swo` - Arquivos temporários vim
- `.DS_Store` - Arquivos do macOS

### 🌐 Frontend (Node.js)
- `node_modules/` - Dependências JavaScript
- `dist/`, `build/` - Build do frontend
- `*.log` - Logs do npm/yarn

### 🔒 Arquivos Sensíveis
- Configurações de produção com API keys
- Certificados SSL
- Credenciais e secrets

## 📁 Estrutura Limpa

```
trading_bot/
├── 📄 .gitignore (NOVO)
├── 📊 config.yaml (único config ativo)
├── 🤖 src/ (código Python limpo)
├── 📊 web-dashboard/ (frontend)
├── 🔧 bot_manager.sh
├── 📥 install_24_7.sh
├── 💊 healthcheck.sh
└── 📖 documentação
```

## 🧹 Limpeza Realizada

### ❌ Removidos:
- `config_***.yaml` - Configs antigos/duplicados
- `trader_new.py` - Arquivo não utilizado
- `simple_websocket.py` - Substituído por ultra_simple_websocket.py
- `test_commands.py` - Script de teste obsoleto
- `frontend/` - Pasta vazia
- Cache Python (`__pycache__/`)

### ✅ Mantidos:
- Apenas arquivos ativos e essenciais
- Configuração única (`config.yaml`)
- Scripts de sistema funcionais
- Estrutura de desenvolvimento organizada

## 🚀 Benefícios

1. **🔒 Segurança**: API keys e dados sensíveis protegidos
2. **🚀 Performance**: Sem arquivos grandes no Git
3. **🧹 Organização**: Apenas código essencial versionado
4. **👥 Colaboração**: Clone mais rápido e limpo
5. **📦 Deploy**: Build otimizado sem lixo

## 📝 Comandos Úteis

```bash
# Verificar status do Git
git status

# Ver arquivos ignorados
git ls-files --others --ignored --exclude-standard

# Limpeza manual (se necessário)
git clean -fdx  # CUIDADO: Remove tudo não versionado!
```
