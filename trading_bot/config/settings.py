from pydantic import BaseModel, Field
from typing import Dict, Optional, List
import os
from dotenv import load_dotenv

load_dotenv()

class ExchangeConfig(BaseModel):
    api_key: str
    api_secret: str
    testnet: bool = True
    rate_limit: int = 10

class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str
    allowed_users: List[str] = []

class TradingConfig(BaseModel):
    max_position_size: float = 0.1
    risk_per_trade: float = 0.02
    stop_loss_percentage: float = 0.02
    take_profit_percentage: float = 0.04
    leverage: int = 1

class DatabaseConfig(BaseModel):
    url: str = "sqlite:///trading_bot.db"

class Settings(BaseModel):
    exchanges: Dict[str, ExchangeConfig] = {}
    telegram: Optional[TelegramConfig] = None
    trading: TradingConfig = TradingConfig()
    database: DatabaseConfig = DatabaseConfig()
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls()
        
        # Binance
        if os.getenv("BINANCE_API_KEY"):
            settings.exchanges["binance"] = ExchangeConfig(
                api_key=os.getenv("BINANCE_API_KEY"),
                api_secret=os.getenv("BINANCE_API_SECRET"),
                testnet=os.getenv("BINANCE_TESTNET", "true").lower() == "true"
            )
        
        # OKX
        if os.getenv("OKX_API_KEY"):
            settings.exchanges["okx"] = ExchangeConfig(
                api_key=os.getenv("OKX_API_KEY"),
                api_secret=os.getenv("OKX_API_SECRET"),
                testnet=os.getenv("OKX_TESTNET", "true").lower() == "true"
            )
        
        # Bybit
        if os.getenv("BYBIT_API_KEY"):
            settings.exchanges["bybit"] = ExchangeConfig(
                api_key=os.getenv("BYBIT_API_KEY"),
                api_secret=os.getenv("BYBIT_API_SECRET"),
                testnet=os.getenv("BYBIT_TESTNET", "true").lower() == "true"
            )
        
        # Telegram
        if os.getenv("TELEGRAM_BOT_TOKEN"):
            settings.telegram = TelegramConfig(
                bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
                chat_id=os.getenv("TELEGRAM_CHAT_ID"),
                allowed_users=os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",")
            )
        
        return settings

settings = Settings.from_env()