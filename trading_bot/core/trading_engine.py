import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger

from ..config.settings import settings
from ..exchanges import create_exchange, BaseExchange, OrderSide, OrderType
from ..strategies.base import BaseStrategy, TradingSignal, SignalType
from ..telegram_bot import TradingTelegramBot
from ..utils.data_fetcher import DataFetcher

class TradingEngine:
    def __init__(self):
        self.exchanges: Dict[str, BaseExchange] = {}
        self.strategies: Dict[str, BaseStrategy] = {}
        self.data_fetchers: Dict[str, DataFetcher] = {}
        self.telegram_bot: Optional[TradingTelegramBot] = None
        self.is_running = False
        self.active_symbols = set()
        
        self._initialize_exchanges()
        self._initialize_telegram()
    
    def _initialize_exchanges(self):
        for exchange_name, config in settings.exchanges.items():
            try:
                exchange = create_exchange(
                    exchange_name, 
                    config.api_key, 
                    config.api_secret, 
                    config.testnet
                )
                self.exchanges[exchange_name] = exchange
                self.data_fetchers[exchange_name] = DataFetcher(exchange)
                logger.info(f"Initialized {exchange_name} exchange")
            except Exception as e:
                logger.error(f"Failed to initialize {exchange_name}: {e}")
    
    def _initialize_telegram(self):
        if settings.telegram:
            try:
                self.telegram_bot = TradingTelegramBot()
                logger.info("Initialized Telegram bot")
            except Exception as e:
                logger.error(f"Failed to initialize Telegram bot: {e}")
    
    def add_strategy(self, strategy: BaseStrategy, symbols: List[str]):
        self.strategies[strategy.name] = strategy
        self.active_symbols.update(symbols)
        logger.info(f"Added strategy: {strategy.name} for symbols: {symbols}")
    
    def remove_strategy(self, strategy_name: str):
        if strategy_name in self.strategies:
            del self.strategies[strategy_name]
            logger.info(f"Removed strategy: {strategy_name}")
    
    async def start(self):
        if self.is_running:
            logger.warning("Trading engine is already running")
            return
        
        self.is_running = True
        logger.info("Starting trading engine...")
        
        # Start telegram bot in background if configured
        if self.telegram_bot:
            asyncio.create_task(self._run_telegram_bot())
        
        # Start main trading loop
        await self._trading_loop()
    
    async def stop(self):
        logger.info("Stopping trading engine...")
        self.is_running = False
    
    async def _run_telegram_bot(self):
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self.telegram_bot.run
            )
        except Exception as e:
            logger.error(f"Telegram bot error: {e}")
    
    async def _trading_loop(self):
        while self.is_running:
            try:
                await self._process_strategies()
                await asyncio.sleep(60)  # Wait 1 minute between cycles
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(30)  # Wait 30 seconds on error
    
    async def _process_strategies(self):
        for strategy_name, strategy in self.strategies.items():
            try:
                await self._process_strategy(strategy)
            except Exception as e:
                logger.error(f"Error processing strategy {strategy_name}: {e}")
    
    async def _process_strategy(self, strategy: BaseStrategy):
        # Get required timeframes
        timeframes = strategy.get_required_timeframes()
        
        for symbol in self.active_symbols:
            try:
                # Fetch market data for all required timeframes
                for timeframe in timeframes:
                    await self._update_market_data(strategy, symbol, timeframe)
                
                # Get trading signal
                market_data = strategy.get_market_data(symbol, 100)
                if len(market_data) < 20:
                    continue
                
                signal = strategy.analyze(symbol, market_data)
                
                if signal.signal_type != SignalType.HOLD and signal.confidence > 0.6:
                    await self._execute_signal(signal, strategy)
                    
            except Exception as e:
                logger.error(f"Error processing {symbol} for strategy {strategy.name}: {e}")
    
    async def _update_market_data(self, strategy: BaseStrategy, symbol: str, timeframe: str):
        # Use the first available exchange for data fetching
        exchange_name = list(self.exchanges.keys())[0]
        data_fetcher = self.data_fetchers[exchange_name]
        
        try:
            # Fetch last 100 candles
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=100)
            
            market_data = await data_fetcher.fetch_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_time,
                end_date=end_time
            )
            
            strategy.add_market_data(symbol, market_data)
            
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
    
    async def _execute_signal(self, signal: TradingSignal, strategy: BaseStrategy):
        logger.info(f"Executing signal: {signal.signal_type.value} {signal.symbol} @ {signal.price}")
        
        # Choose exchange (use first available for now)
        exchange_name = list(self.exchanges.keys())[0]
        exchange = self.exchanges[exchange_name]
        
        try:
            # Determine order side and type
            if signal.signal_type == SignalType.BUY:
                side = OrderSide.BUY
                order_type = OrderType.MARKET
                
            elif signal.signal_type == SignalType.SELL:
                side = OrderSide.SELL
                order_type = OrderType.MARKET
                
            else:  # Close positions
                await self._close_position(signal, exchange)
                return
            
            # Calculate position size based on risk management
            balances = await exchange.get_balance()
            base_currency_balance = next(
                (b for b in balances if b.symbol in ['USDT', 'USD', 'BUSD']), 
                None
            )
            
            if not base_currency_balance or base_currency_balance.free < 10:
                logger.warning(f"Insufficient balance for trading")
                return
            
            # Calculate position size
            account_balance = base_currency_balance.free
            position_size = strategy.calculate_position_size(
                signal, account_balance, settings.trading.risk_per_trade
            )
            
            # Place main order
            order = await exchange.create_order(
                symbol=signal.symbol,
                side=side,
                order_type=order_type,
                amount=position_size,
                price=signal.price if order_type == OrderType.LIMIT else None
            )
            
            logger.info(f"Order placed: {order.id}")
            
            # Place stop loss and take profit if specified
            if signal.stop_loss:
                await self._place_stop_loss(signal, exchange, position_size)
            
            if signal.take_profit:
                await self._place_take_profit(signal, exchange, position_size)
            
            # Send telegram notification
            if self.telegram_bot:
                await self._send_trade_notification(signal, order, exchange_name)
                
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            if self.telegram_bot:
                await self.telegram_bot.send_notification(
                    f"❌ **Trade Execution Failed**\\n"
                    f"Symbol: {signal.symbol}\\n"
                    f"Error: {str(e)}"
                )
    
    async def _close_position(self, signal: TradingSignal, exchange: BaseExchange):
        try:
            positions = await exchange.get_positions()
            position = next(
                (p for p in positions if p.symbol == signal.symbol), 
                None
            )
            
            if not position or position.size == 0:
                logger.warning(f"No position found for {signal.symbol}")
                return
            
            # Determine close side
            close_side = OrderSide.SELL if position.side == "long" else OrderSide.BUY
            
            # Place close order
            order = await exchange.create_order(
                symbol=signal.symbol,
                side=close_side,
                order_type=OrderType.MARKET,
                amount=position.size
            )
            
            logger.info(f"Position closed: {order.id}")
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
    
    async def _place_stop_loss(self, signal: TradingSignal, exchange: BaseExchange, amount: float):
        try:
            stop_side = OrderSide.SELL if signal.signal_type == SignalType.BUY else OrderSide.BUY
            
            await exchange.create_stop_loss_order(
                symbol=signal.symbol,
                side=stop_side,
                amount=amount,
                stop_price=signal.stop_loss
            )
            
            logger.info(f"Stop loss placed at {signal.stop_loss}")
            
        except Exception as e:
            logger.error(f"Error placing stop loss: {e}")
    
    async def _place_take_profit(self, signal: TradingSignal, exchange: BaseExchange, amount: float):
        try:
            tp_side = OrderSide.SELL if signal.signal_type == SignalType.BUY else OrderSide.BUY
            
            await exchange.create_take_profit_order(
                symbol=signal.symbol,
                side=tp_side,
                amount=amount,
                price=signal.take_profit
            )
            
            logger.info(f"Take profit placed at {signal.take_profit}")
            
        except Exception as e:
            logger.error(f"Error placing take profit: {e}")
    
    async def _send_trade_notification(self, signal: TradingSignal, order, exchange_name: str):
        try:
            side_emoji = "🟢" if signal.signal_type == SignalType.BUY else "🔴"
            message = f"{side_emoji} **Trade Executed**\\n\\n"
            message += f"Exchange: {exchange_name.upper()}\\n"
            message += f"Symbol: `{signal.symbol}`\\n"
            message += f"Side: {signal.signal_type.value.upper()}\\n"
            message += f"Amount: {signal.amount}\\n"
            message += f"Price: ${signal.price:.4f}\\n"
            message += f"Confidence: {signal.confidence:.1%}\\n"
            message += f"Order ID: `{order.id}`\\n"
            
            if signal.stop_loss:
                message += f"Stop Loss: ${signal.stop_loss:.4f}\\n"
            if signal.take_profit:
                message += f"Take Profit: ${signal.take_profit:.4f}\\n"
            
            await self.telegram_bot.send_notification(message)
            
        except Exception as e:
            logger.error(f"Error sending trade notification: {e}")
    
    async def get_portfolio_status(self) -> Dict:
        portfolio = {}
        
        for exchange_name, exchange in self.exchanges.items():
            try:
                balances = await exchange.get_balance()
                positions = await exchange.get_positions()
                
                portfolio[exchange_name] = {
                    'balances': [
                        {
                            'symbol': b.symbol,
                            'free': b.free,
                            'used': b.used,
                            'total': b.total
                        } for b in balances if b.total > 0
                    ],
                    'positions': [
                        {
                            'symbol': p.symbol,
                            'side': p.side,
                            'size': p.size,
                            'entry_price': p.entry_price,
                            'unrealized_pnl': p.unrealized_pnl,
                            'percentage': p.percentage
                        } for p in positions
                    ]
                }
                
            except Exception as e:
                logger.error(f"Error getting portfolio status for {exchange_name}: {e}")
                portfolio[exchange_name] = {'error': str(e)}
        
        return portfolio