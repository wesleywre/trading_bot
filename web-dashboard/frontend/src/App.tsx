import axios from 'axios';
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  DollarSign,
  Pause,
  Play,
  RotateCcw,
  TrendingDown,
  TrendingUp,
  Wifi,
  WifiOff,
  Zap
} from 'lucide-react';
import { useEffect, useState } from 'react';

// Types
interface BotStatus {
  is_running: boolean;
  pid?: number;
  uptime: string;
  memory_usage: number;
  cpu_usage: number;
  websocket_connected: boolean;
  last_update: string;
}

interface TradingPair {
  symbol: string;
  current_price: number;
  change_24h: number;
  volume_24h: number;
  last_signal: string;
  strategy: string;
  pnl: number;
  status: string;
}

interface Portfolio {
  total_balance: number;
  available_balance: number;
  in_positions: number;
  total_pnl: number;
  daily_pnl: number;
  positions: any[];
}

interface LogEntry {
  timestamp: string;
  level: string;
  source: string;
  message: string;
}

// Componente principal
function App() {
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [tradingPairs, setTradingPairs] = useState<TradingPair[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [darkMode, setDarkMode] = useState(true);

  // Buscar dados da API
  const fetchData = async () => {
    try {
      const [statusRes, pairsRes, portfolioRes, logsRes] = await Promise.all([
        axios.get('/api/bot/status'),
        axios.get('/api/trading/pairs'),
        axios.get('/api/portfolio'),
        axios.get('/api/logs?limit=20')
      ]);

      setBotStatus(statusRes.data);
      setTradingPairs(pairsRes.data);
      setPortfolio(portfolioRes.data);
      setLogs(logsRes.data.logs);
      setLoading(false);
    } catch (error) {
      console.error('Erro ao buscar dados:', error);
      setLoading(false);
    }
  };

  // Controle do bot
  const controlBot = async (action: 'start' | 'stop' | 'restart') => {
    try {
      await axios.post(`/api/bot/${action}`);
      setTimeout(fetchData, 2000); // Atualiza depois de 2s
    } catch (error) {
      console.error(`Erro ao ${action} bot:`, error);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Atualiza a cada 5s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-white text-xl">🚀 Carregando Trading Bot Dashboard...</div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen ${darkMode ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-900'}`}>
      {/* Header */}
      <header className="bg-gradient-to-r from-blue-600 to-purple-600 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <Activity className="h-8 w-8 text-white mr-3" />
              <h1 className="text-2xl font-bold text-white">Trading Bot Dashboard</h1>
            </div>

            <div className="flex items-center space-x-4">
              {/* Status do Bot */}
              <div className="flex items-center space-x-2">
                {botStatus?.is_running ? (
                  <CheckCircle2 className="h-5 w-5 text-green-400" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-red-400" />
                )}
                <span className="text-sm text-gray-200">
                  {botStatus?.is_running ? 'Online' : 'Offline'}
                </span>
              </div>

              {/* WebSocket Status */}
              <div className="flex items-center space-x-2">
                {botStatus?.websocket_connected ? (
                  <Wifi className="h-5 w-5 text-green-400" />
                ) : (
                  <WifiOff className="h-5 w-5 text-red-400" />
                )}
                <span className="text-sm text-gray-200">
                  {botStatus?.websocket_connected ? 'Real-time' : 'Disconnected'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Controles do Bot */}
        <div className="mb-6">
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold mb-2">Controle do Bot</h2>
                <div className="flex items-center space-x-4 text-sm text-gray-300">
                  <span>Status: {botStatus?.is_running ? '✅ Rodando' : '❌ Parado'}</span>
                  <span>PID: {botStatus?.pid || 'N/A'}</span>
                  <span>Uptime: {botStatus?.uptime}</span>
                  <span>RAM: {botStatus?.memory_usage?.toFixed(1)}MB</span>
                  <span>CPU: {botStatus?.cpu_usage?.toFixed(1)}%</span>
                </div>
              </div>

              <div className="flex space-x-2">
                <button
                  onClick={() => controlBot('start')}
                  className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg flex items-center space-x-2"
                  disabled={botStatus?.is_running}
                >
                  <Play className="h-4 w-4" />
                  <span>Start</span>
                </button>

                <button
                  onClick={() => controlBot('stop')}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg flex items-center space-x-2"
                  disabled={!botStatus?.is_running}
                >
                  <Pause className="h-4 w-4" />
                  <span>Stop</span>
                </button>

                <button
                  onClick={() => controlBot('restart')}
                  className="bg-yellow-600 hover:bg-yellow-700 text-white px-4 py-2 rounded-lg flex items-center space-x-2"
                >
                  <RotateCcw className="h-4 w-4" />
                  <span>Restart</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Portfolio */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Balance Total</p>
                <p className="text-2xl font-bold text-green-400">
                  ${portfolio?.total_balance?.toLocaleString() || '0'}
                </p>
              </div>
              <DollarSign className="h-8 w-8 text-green-400" />
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Disponível</p>
                <p className="text-2xl font-bold text-blue-400">
                  ${portfolio?.available_balance?.toLocaleString() || '0'}
                </p>
              </div>
              <Zap className="h-8 w-8 text-blue-400" />
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Em Posições</p>
                <p className="text-2xl font-bold text-yellow-400">
                  ${portfolio?.in_positions?.toLocaleString() || '0'}
                </p>
              </div>
              <Activity className="h-8 w-8 text-yellow-400" />
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">P&L Total</p>
                <p className={`text-2xl font-bold ${(portfolio?.total_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {(portfolio?.total_pnl || 0) >= 0 ? '+' : ''}${portfolio?.total_pnl?.toFixed(2) || '0.00'}
                </p>
              </div>
              {(portfolio?.total_pnl || 0) >= 0 ? (
                <TrendingUp className="h-8 w-8 text-green-400" />
              ) : (
                <TrendingDown className="h-8 w-8 text-red-400" />
              )}
            </div>
          </div>
        </div>

        {/* Trading Pairs */}
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-4">Pares de Trading</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {tradingPairs.map((pair, index) => (
              <div key={index} className="bg-gray-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-lg font-semibold">{pair.symbol}</h3>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${pair.last_signal === 'COMPRA' ? 'bg-green-600 text-green-100' :
                      pair.last_signal === 'VENDA' ? 'bg-red-600 text-red-100' :
                        'bg-gray-600 text-gray-100'
                    }`}>
                    {pair.last_signal}
                  </span>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Preço:</span>
                    <span className="font-medium">${pair.current_price?.toFixed(4) || '0'}</span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-400">24h:</span>
                    <span className={`font-medium ${pair.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {pair.change_24h >= 0 ? '+' : ''}{pair.change_24h?.toFixed(2) || '0'}%
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-400">Estratégia:</span>
                    <span className="font-medium text-blue-400">{pair.strategy}</span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-400">Status:</span>
                    <span className="font-medium">{pair.status}</span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-400">P&L:</span>
                    <span className={`font-medium ${pair.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {pair.pnl >= 0 ? '+' : ''}${pair.pnl?.toFixed(2) || '0.00'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Logs */}
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-4">Logs Recentes</h2>
          <div className="bg-gray-800 rounded-lg p-4 max-h-96 overflow-y-auto">
            {logs.length === 0 ? (
              <p className="text-gray-400 text-center">Nenhum log encontrado</p>
            ) : (
              <div className="space-y-2 font-mono text-sm">
                {logs.map((log, index) => (
                  <div key={index} className={`flex items-start space-x-3 p-2 rounded ${log.level === 'ERROR' ? 'bg-red-900/20' :
                      log.level === 'WARNING' ? 'bg-yellow-900/20' :
                        log.level === 'INFO' ? 'bg-blue-900/20' :
                          'bg-gray-700/20'
                    }`}>
                    <span className="text-gray-400 text-xs whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                    <span className={`text-xs px-2 py-1 rounded ${log.level === 'ERROR' ? 'bg-red-600' :
                        log.level === 'WARNING' ? 'bg-yellow-600' :
                          log.level === 'INFO' ? 'bg-blue-600' :
                            'bg-gray-600'
                      }`}>
                      {log.level}
                    </span>
                    <span className="flex-1 text-gray-300">{log.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
