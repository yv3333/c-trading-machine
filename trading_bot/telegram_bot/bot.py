import asyncio
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from typing import Dict, List, Optional
from loguru import logger
import json

from ..config.settings import settings
from ..exchanges import create_exchange, BaseExchange

class TradingTelegramBot:
    def __init__(self):
        self.bot_token = settings.telegram.bot_token if settings.telegram else None
        self.chat_id = settings.telegram.chat_id if settings.telegram else None
        self.allowed_users = settings.telegram.allowed_users if settings.telegram else []
        
        if not self.bot_token:
            raise ValueError("Telegram bot token not configured")
        
        self.app = Application.builder().token(self.bot_token).build()
        self.exchanges: Dict[str, BaseExchange] = {}
        
        # Initialize exchanges
        for exchange_name, config in settings.exchanges.items():
            try:
                self.exchanges[exchange_name] = create_exchange(
                    exchange_name, config.api_key, config.api_secret, config.testnet
                )
                logger.info(f"Initialized {exchange_name} exchange")
            except Exception as e:
                logger.error(f"Failed to initialize {exchange_name}: {e}")
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("balance", self.balance_command))
        self.app.add_handler(CommandHandler("positions", self.positions_command))
        self.app.add_handler(CommandHandler("orders", self.orders_command))
        self.app.add_handler(CommandHandler("buy", self.buy_command))
        self.app.add_handler(CommandHandler("sell", self.sell_command))
        self.app.add_handler(CommandHandler("cancel", self.cancel_command))
        self.app.add_handler(CommandHandler("price", self.price_command))
        self.app.add_handler(CommandHandler("leverage", self.leverage_command))
        
        # Handle unknown commands
        self.app.add_handler(MessageHandler(filters.COMMAND, self.unknown_command))
    
    def _check_user_permission(self, update: Update) -> bool:
        user_id = str(update.effective_user.id)
        username = update.effective_user.username
        
        if self.allowed_users and user_id not in self.allowed_users and username not in self.allowed_users:
            logger.warning(f"Unauthorized access attempt by user {user_id} ({username})")
            return False
        return True
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_user_permission(update):
            await update.message.reply_text("❌ Unauthorized access!")
            return
        
        welcome_message = """
🤖 **Trading Bot Started!**

Available commands:
/help - Show this help message
/balance [exchange] - Show account balance
/positions [exchange] - Show open positions
/orders [exchange] - Show open orders
/buy <exchange> <symbol> <amount> [price] - Place buy order
/sell <exchange> <symbol> <amount> [price] - Place sell order
/cancel <exchange> <order_id> <symbol> - Cancel order
/price <exchange> <symbol> - Get current price
/leverage <exchange> <symbol> <leverage> - Set leverage

Supported exchanges: {}
        """.format(", ".join(self.exchanges.keys()))
        
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_user_permission(update):
            return
        await self.start_command(update, context)
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_user_permission(update):
            await update.message.reply_text("❌ Unauthorized access!")
            return
        
        exchange_name = context.args[0] if context.args else list(self.exchanges.keys())[0]
        
        if exchange_name not in self.exchanges:
            await update.message.reply_text(f"❌ Exchange {exchange_name} not configured")
            return
        
        try:
            exchange = self.exchanges[exchange_name]
            balances = await exchange.get_balance()
            
            message = f"💰 **{exchange_name.upper()} Balance:**\\n\\n"
            for balance in balances:
                if balance.total > 0:
                    message += f"`{balance.symbol}`: {balance.free:.6f} (Free) | {balance.used:.6f} (Used)\\n"
            
            if not any(b.total > 0 for b in balances):
                message += "No balances found"
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            await update.message.reply_text(f"❌ Error fetching balance: {str(e)}")
    
    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_user_permission(update):
            await update.message.reply_text("❌ Unauthorized access!")
            return
        
        exchange_name = context.args[0] if context.args else list(self.exchanges.keys())[0]
        
        if exchange_name not in self.exchanges:
            await update.message.reply_text(f"❌ Exchange {exchange_name} not configured")
            return
        
        try:
            exchange = self.exchanges[exchange_name]
            positions = await exchange.get_positions()
            
            message = f"📊 **{exchange_name.upper()} Positions:**\\n\\n"
            for position in positions:
                pnl_emoji = "🟢" if position.unrealized_pnl >= 0 else "🔴"
                message += f"{pnl_emoji} `{position.symbol}` ({position.side})\\n"
                message += f"Size: {position.size:.6f}\\n"
                message += f"Entry: ${position.entry_price:.4f}\\n"
                message += f"PnL: ${position.unrealized_pnl:.2f} ({position.percentage:.2f}%)\\n"
                message += f"Leverage: {position.leverage}x\\n\\n"
            
            if not positions:
                message += "No open positions"
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            await update.message.reply_text(f"❌ Error fetching positions: {str(e)}")
    
    async def orders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_user_permission(update):
            await update.message.reply_text("❌ Unauthorized access!")
            return
        
        exchange_name = context.args[0] if context.args else list(self.exchanges.keys())[0]
        
        if exchange_name not in self.exchanges:
            await update.message.reply_text(f"❌ Exchange {exchange_name} not configured")
            return
        
        try:
            exchange = self.exchanges[exchange_name]
            orders = await exchange.get_open_orders()
            
            message = f"📋 **{exchange_name.upper()} Open Orders:**\\n\\n"
            for order in orders:
                side_emoji = "🟢" if order.side.value == "buy" else "🔴"
                message += f"{side_emoji} `{order.symbol}` - {order.type.value.upper()}\\n"
                message += f"Side: {order.side.value.upper()}\\n"
                message += f"Amount: {order.amount:.6f}\\n"
                if order.price:
                    message += f"Price: ${order.price:.4f}\\n"
                message += f"Status: {order.status.value}\\n"
                message += f"ID: `{order.id}`\\n\\n"
            
            if not orders:
                message += "No open orders"
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            await update.message.reply_text(f"❌ Error fetching orders: {str(e)}")
    
    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_user_permission(update):
            await update.message.reply_text("❌ Unauthorized access!")
            return
        
        if len(context.args) < 3:
            await update.message.reply_text("❌ Usage: /buy <exchange> <symbol> <amount> [price]")
            return
        
        exchange_name = context.args[0]
        symbol = context.args[1]
        amount = float(context.args[2])
        price = float(context.args[3]) if len(context.args) > 3 else None
        
        await self._place_order(update, exchange_name, symbol, "buy", amount, price)
    
    async def sell_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_user_permission(update):
            await update.message.reply_text("❌ Unauthorized access!")
            return
        
        if len(context.args) < 3:
            await update.message.reply_text("❌ Usage: /sell <exchange> <symbol> <amount> [price]")
            return
        
        exchange_name = context.args[0]
        symbol = context.args[1]
        amount = float(context.args[2])
        price = float(context.args[3]) if len(context.args) > 3 else None
        
        await self._place_order(update, exchange_name, symbol, "sell", amount, price)
    
    async def _place_order(self, update: Update, exchange_name: str, symbol: str, side: str, amount: float, price: Optional[float]):
        if exchange_name not in self.exchanges:
            await update.message.reply_text(f"❌ Exchange {exchange_name} not configured")
            return
        
        try:
            exchange = self.exchanges[exchange_name]
            from ..exchanges.base import OrderSide, OrderType
            
            order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
            order_type = OrderType.LIMIT if price else OrderType.MARKET
            
            order = await exchange.create_order(symbol, order_side, order_type, amount, price)
            
            side_emoji = "🟢" if side == "buy" else "🔴"
            message = f"{side_emoji} **Order Placed!**\\n\\n"
            message += f"Exchange: {exchange_name.upper()}\\n"
            message += f"Symbol: `{symbol}`\\n"
            message += f"Side: {side.upper()}\\n"
            message += f"Amount: {amount}\\n"
            if price:
                message += f"Price: ${price}\\n"
            message += f"Type: {order_type.value.upper()}\\n"
            message += f"Order ID: `{order.id}`\\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            await update.message.reply_text(f"❌ Error placing order: {str(e)}")
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_user_permission(update):
            await update.message.reply_text("❌ Unauthorized access!")
            return
        
        if len(context.args) < 3:
            await update.message.reply_text("❌ Usage: /cancel <exchange> <order_id> <symbol>")
            return
        
        exchange_name = context.args[0]
        order_id = context.args[1]
        symbol = context.args[2]
        
        if exchange_name not in self.exchanges:
            await update.message.reply_text(f"❌ Exchange {exchange_name} not configured")
            return
        
        try:
            exchange = self.exchanges[exchange_name]
            success = await exchange.cancel_order(order_id, symbol)
            
            if success:
                await update.message.reply_text(f"✅ Order `{order_id}` cancelled successfully")
            else:
                await update.message.reply_text(f"❌ Failed to cancel order `{order_id}`")
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            await update.message.reply_text(f"❌ Error cancelling order: {str(e)}")
    
    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_user_permission(update):
            await update.message.reply_text("❌ Unauthorized access!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("❌ Usage: /price <exchange> <symbol>")
            return
        
        exchange_name = context.args[0]
        symbol = context.args[1]
        
        if exchange_name not in self.exchanges:
            await update.message.reply_text(f"❌ Exchange {exchange_name} not configured")
            return
        
        try:
            exchange = self.exchanges[exchange_name]
            ticker = await exchange.get_ticker(symbol)
            
            change_emoji = "🟢" if ticker.change >= 0 else "🔴"
            message = f"💲 **{symbol} Price on {exchange_name.upper()}:**\\n\\n"
            message += f"{change_emoji} **${ticker.price:.4f}**\\n"
            message += f"Change: {ticker.change:.2f}%\\n"
            message += f"Volume: {ticker.volume:.2f}\\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error fetching price: {e}")
            await update.message.reply_text(f"❌ Error fetching price: {str(e)}")
    
    async def leverage_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_user_permission(update):
            await update.message.reply_text("❌ Unauthorized access!")
            return
        
        if len(context.args) < 3:
            await update.message.reply_text("❌ Usage: /leverage <exchange> <symbol> <leverage>")
            return
        
        exchange_name = context.args[0]
        symbol = context.args[1]
        leverage = int(context.args[2])
        
        if exchange_name not in self.exchanges:
            await update.message.reply_text(f"❌ Exchange {exchange_name} not configured")
            return
        
        try:
            exchange = self.exchanges[exchange_name]
            success = await exchange.set_leverage(symbol, leverage)
            
            if success:
                await update.message.reply_text(f"✅ Leverage for `{symbol}` set to {leverage}x")
            else:
                await update.message.reply_text(f"❌ Failed to set leverage for `{symbol}`")
        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            await update.message.reply_text(f"❌ Error setting leverage: {str(e)}")
    
    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_user_permission(update):
            return
        await update.message.reply_text("❌ Unknown command. Use /help to see available commands.")
    
    async def send_notification(self, message: str):
        if not self.chat_id:
            logger.warning("No chat ID configured for notifications")
            return
        
        try:
            bot = Bot(token=self.bot_token)
            await bot.send_message(chat_id=self.chat_id, text=message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    def run(self):
        logger.info("Starting Telegram bot...")
        self.app.run_polling()
    
    async def start_webhook(self, webhook_url: str):
        logger.info(f"Starting Telegram bot with webhook: {webhook_url}")
        await self.app.start()
        await self.app.updater.start_webhook(
            listen="0.0.0.0",
            port=8080,
            webhook_url=webhook_url
        )