from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    PARTIAL = "partial"

@dataclass
class Balance:
    symbol: str
    free: float
    used: float
    total: float

@dataclass
class Order:
    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    amount: float
    price: Optional[float]
    status: OrderStatus
    timestamp: int
    filled: float = 0.0
    remaining: float = 0.0
    fee: Optional[Dict] = None

@dataclass
class Position:
    symbol: str
    side: str
    size: float
    entry_price: float
    unrealized_pnl: float
    percentage: float
    leverage: int

@dataclass
class Ticker:
    symbol: str
    price: float
    volume: float
    change: float
    timestamp: int

class BaseExchange(ABC):
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.name = self.__class__.__name__.lower().replace('exchange', '')
    
    @abstractmethod
    async def get_balance(self) -> List[Balance]:
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        pass
    
    @abstractmethod
    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType, 
                          amount: float, price: Optional[float] = None) -> Order:
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Order:
        pass
    
    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        pass
    
    @abstractmethod
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        pass
    
    @abstractmethod
    async def create_stop_loss_order(self, symbol: str, side: OrderSide, 
                                   amount: float, stop_price: float) -> Order:
        pass
    
    @abstractmethod
    async def create_take_profit_order(self, symbol: str, side: OrderSide, 
                                     amount: float, price: float) -> Order:
        pass