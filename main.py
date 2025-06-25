#!/usr/bin/env python3
import asyncio
import argparse
from datetime import datetime, timedelta

from trading_bot.core import TradingEngine
from trading_bot.strategies import get_strategy
from trading_bot.backtesting import BacktestEngine
from trading_bot.utils import setup_logger, DataFetcher
from trading_bot.config.settings import settings
from trading_bot.exchanges import create_exchange

async def run_live_trading():
    setup_logger(level=settings.log_level, log_file="trading_bot/logs/trading.log")
    
    engine = TradingEngine()
    
    # Add strategies
    ma_strategy = get_strategy("ma_crossover", fast_period=10, slow_period=20)
    rsi_strategy = get_strategy("rsi", rsi_period=14)
    
    # Define symbols to trade
    symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]
    
    engine.add_strategy(ma_strategy, symbols)
    engine.add_strategy(rsi_strategy, symbols)
    
    print("🚀 Starting live trading...")
    print(f"📊 Active strategies: {list(engine.strategies.keys())}")
    print(f"💰 Trading symbols: {symbols}")
    print(f"🏢 Exchanges: {list(engine.exchanges.keys())}")
    
    try:
        await engine.start()
    except KeyboardInterrupt:
        print("\\n⏹️  Stopping trading engine...")
        await engine.stop()
        print("✅ Trading engine stopped")

async def run_backtest(strategy_name: str, symbol: str, days: int = 30):
    setup_logger(level="INFO")
    
    print(f"🔍 Running backtest for {strategy_name} on {symbol}")
    
    # Initialize exchange for data fetching
    if not settings.exchanges:
        print("❌ No exchanges configured. Please set up API keys.")
        return
    
    exchange_name = list(settings.exchanges.keys())[0]
    exchange_config = settings.exchanges[exchange_name]
    
    exchange = create_exchange(
        exchange_name, 
        exchange_config.api_key, 
        exchange_config.api_secret, 
        exchange_config.testnet
    )
    
    # Fetch historical data
    data_fetcher = DataFetcher(exchange)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    print(f"📈 Fetching data from {start_date.date()} to {end_date.date()}")
    
    market_data = await data_fetcher.fetch_historical_data(
        symbol=symbol,
        timeframe="1h",
        start_date=start_date,
        end_date=end_date
    )
    
    if not market_data:
        print("❌ No market data found")
        return
    
    print(f"✅ Fetched {len(market_data)} data points")
    
    # Initialize strategy
    if strategy_name == "ma_crossover":
        strategy = get_strategy("ma_crossover", fast_period=10, slow_period=20)
    elif strategy_name == "rsi":
        strategy = get_strategy("rsi", rsi_period=14)
    else:
        print(f"❌ Unknown strategy: {strategy_name}")
        return
    
    # Run backtest
    backtest_engine = BacktestEngine(initial_balance=10000.0, commission=0.001)
    
    result = backtest_engine.run_backtest(
        strategy=strategy,
        market_data={symbol: market_data},
        start_date=start_date,
        end_date=end_date
    )
    
    # Print results
    print("\\n" + "="*50)
    print("📊 BACKTEST RESULTS")
    print("="*50)
    print(f"Strategy: {strategy_name}")
    print(f"Symbol: {symbol}")
    print(f"Period: {result.start_date.date()} to {result.end_date.date()} ({result.duration_days} days)")
    print(f"\\nPerformance:")
    print(f"  Initial Balance: ${result.initial_balance:,.2f}")
    print(f"  Final Balance: ${result.final_balance:,.2f}")
    print(f"  Total Return: ${result.total_return:,.2f} ({result.total_return_pct:.2f}%)")
    print(f"  Max Drawdown: ${result.max_drawdown:,.2f} ({result.max_drawdown_pct:.2f}%)")
    print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"\\nTrade Statistics:")
    print(f"  Total Trades: {result.total_trades}")
    print(f"  Winning Trades: {result.winning_trades}")
    print(f"  Losing Trades: {result.losing_trades}")
    print(f"  Win Rate: {result.win_rate:.1f}%")
    print(f"  Average Win: ${result.avg_win:.2f}")
    print(f"  Average Loss: ${result.avg_loss:.2f}")
    print(f"  Profit Factor: {result.profit_factor:.2f}")
    
    # Show recent trades
    if result.trades:
        print(f"\\nRecent Trades (last 5):")
        for trade in result.trades[-5:]:
            pnl_emoji = "🟢" if trade['pnl'] >= 0 else "🔴"
            print(f"  {pnl_emoji} {trade['side'].upper()} {trade['symbol']} | "
                  f"Entry: ${trade['entry_price']:.4f} | "
                  f"Exit: ${trade['exit_price']:.4f} | "
                  f"P&L: ${trade['pnl']:.2f} ({trade['return_pct']:.2f}%)")

def main():
    parser = argparse.ArgumentParser(description="Trading Bot")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Live trading command
    live_parser = subparsers.add_parser('live', help='Run live trading')
    
    # Backtest command
    backtest_parser = subparsers.add_parser('backtest', help='Run backtest')
    backtest_parser.add_argument('--strategy', required=True, 
                               choices=['ma_crossover', 'rsi'],
                               help='Strategy to backtest')
    backtest_parser.add_argument('--symbol', required=True,
                                help='Symbol to backtest (e.g., BTC/USDT)')
    backtest_parser.add_argument('--days', type=int, default=30,
                                help='Number of days to backtest (default: 30)')
    
    args = parser.parse_args()
    
    if args.command == 'live':
        asyncio.run(run_live_trading())
    elif args.command == 'backtest':
        asyncio.run(run_backtest(args.strategy, args.symbol, args.days))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()