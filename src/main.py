import logging

import colorama

from config_manager import ConfigManager, TradingProfile
from strategies import StrategyFactory
from trader import MultiPairTrader


def setup_logging(config_manager: ConfigManager):
    """Configura o sistema de logging."""
    logging_config = config_manager.get_logging_config()
    colorama.init(autoreset=True)

    # Remove handlers existentes
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Configura logging
    logging.basicConfig(
        level=getattr(logging, logging_config.get("level", "INFO")),
        format=logging_config.get("format", "%(asctime)s - %(levelname)s - %(message)s"),
        handlers=[
            logging.FileHandler(logging_config.get("file", "trading_bot.log"), mode="w"),
            logging.StreamHandler(),
        ],
        force=True,
    )

    # Log de teste
    logging.info("🔧 Sistema de logging configurado com sucesso")


def main():
    """Função principal que inicializa e executa o bot."""
    try:
        print("🔄 Iniciando Trading Bot...")

        # Inicializa gerenciador de configuração
        config_manager = ConfigManager("config.yaml")

        # Carrega configurações
        config = config_manager.load_config()
        setup_logging(config_manager)

        print("🚀 Trading Bot inicializado com arquitetura modular")
        logging.info("🚀 Inicializando Trading Bot com arquitetura modular")

        # Define perfil de trading (pode ser configurável)
        trading_profile = TradingProfile.MODERATE
        config_manager.set_trading_profile(trading_profile)
        print(f"📊 Perfil de trading: {trading_profile.value}")
        logging.info(f"📊 Perfil de trading: {trading_profile.value}")

        # Extrai configurações específicas
        exchange_config = config_manager.get_exchange_config()
        market_config = config_manager.get_market_monitoring_config()

        print("⚙️ Configurações carregadas com sucesso")

        # Inicializa o trader multi-par
        print("📡 Conectando à exchange Binance (testnet)...")
        trader = MultiPairTrader(exchange_config, market_config, config)

        # Adiciona os pares de trading usando o factory
        asset_configs = config_manager.get_asset_configs()

        print(f"🎯 Configurando {len(asset_configs)} pares de trading...")

        for asset_config in asset_configs:
            try:
                # Usa o factory para criar a estratégia
                strategy = StrategyFactory.create_strategy(
                    symbol=asset_config.symbol,
                    strategy_name=asset_config.strategy,
                    params=asset_config.strategy_params,
                )

                # Obtém configuração de risco específica para o tipo de ativo
                risk_config = config_manager.get_risk_config(asset_config.asset_type)

                trader.add_trading_pair(
                    asset_config.symbol,
                    strategy,
                    asset_config.amount,
                )

                print(
                    f"✅ {asset_config.symbol} configurado:\n"
                    f"   📈 Estratégia: {asset_config.strategy} ({asset_config.asset_type})\n"
                    f"   💰 Amount: {asset_config.amount}\n"
                    f"   🛡️ Stop Loss: {risk_config.stop_loss_percentage:.1%}\n"
                    f"   🎯 Take Profit: {risk_config.take_profit_percentage:.1%}"
                )

                logging.info(
                    f"✅ {asset_config.symbol} configurado:\n"
                    f"   📈 Estratégia: {asset_config.strategy} ({asset_config.asset_type})\n"
                    f"   💰 Amount: {asset_config.amount}\n"
                    f"   🛡️ Stop Loss: {risk_config.stop_loss_percentage:.1%}\n"
                    f"   🎯 Take Profit: {risk_config.take_profit_percentage:.1%}"
                )

            except ValueError as e:
                error_msg = f"❌ Erro ao configurar {asset_config.symbol}: {e}"
                print(error_msg)
                logging.error(error_msg)
                # Lista estratégias disponíveis
                available = StrategyFactory.get_recommended_strategies(asset_config.symbol)
                available_msg = f"💡 Estratégias disponíveis: {list(available.keys())}"
                print(available_msg)
                logging.info(available_msg)
                continue

        # Inicia o trading
        print("🎯 Iniciando operações de trading...")
        print("📊 Bot será executado em background enquanto você usa os comandos...")
        logging.info("🎯 Iniciando operações de trading...")

        trader.start()
        print("✅ Bot iniciado com sucesso! Use 'activity' para ver a atividade.")

        # Mantém o programa rodando
        try:
            while True:
                command = (
                    input(
                        "\n📋 Comandos disponíveis:\n"
                        "  [ENTER] - Ver resumo da conta\n"
                        "  'status' - Status detalhado\n"
                        "  'activity' - Ver atividade recente\n"
                        "  'live' - Monitorar logs em tempo real (10 últimas linhas)\n"
                        "  'config' - Salvar configuração atual\n"
                        "  'profile <conservative|moderate|aggressive>' - Mudar perfil\n"
                        "  'quit' - Sair\n"
                        ">>> "
                    )
                    .strip()
                    .lower()
                )

                if command == "quit":
                    break
                elif command == "":
                    trader.print_account_summary()
                elif command == "status":
                    trader.print_account_summary()
                elif command == "activity":
                    # Mostra as últimas 10 linhas do log
                    try:
                        with open("trading_bot.log", "r") as f:
                            lines = f.readlines()
                            print("\n📊 Atividade recente (últimas 10 linhas):")
                            print("-" * 60)
                            for line in lines[-10:]:
                                print(line.strip())
                            print("-" * 60)
                    except FileNotFoundError:
                        print("❌ Arquivo de log não encontrado")
                elif command == "live":
                    # Mostra logs em tempo real
                    import subprocess

                    print("📊 Monitorando logs em tempo real (Ctrl+C para parar)...")
                    print("-" * 60)
                    try:
                        subprocess.run(["tail", "-f", "trading_bot.log"], check=True)
                    except KeyboardInterrupt:
                        print("\n" + "-" * 60)
                        print("📋 Voltando ao menu principal...")
                    except FileNotFoundError:
                        print("❌ Arquivo de log não encontrado")
                elif command == "config":
                    config_manager.save_config()
                elif command.startswith("profile "):
                    profile_name = command.split(" ", 1)[1]
                    try:
                        new_profile = TradingProfile(profile_name)
                        config_manager.set_trading_profile(new_profile)
                        print(f"✅ Perfil alterado para: {new_profile.value}")
                        logging.info(f"✅ Perfil alterado para: {new_profile.value}")
                    except ValueError:
                        print("❌ Perfil inválido. Opções: conservative, moderate, aggressive")
                        logging.error(
                            "❌ Perfil inválido. Opções: conservative, moderate, aggressive"
                        )
                else:
                    print("❓ Comando não reconhecido")
                    logging.info("❓ Comando não reconhecido")

        except KeyboardInterrupt:
            logging.info("⏹️ Interrupção solicitada pelo usuário")

        logging.info("🔄 Encerrando o bot...")
        trader.stop()

    except Exception as e:
        logging.error(f"💥 Erro fatal: {str(e)}")
        if "trader" in locals():
            trader.stop()


if __name__ == "__main__":
    main()
