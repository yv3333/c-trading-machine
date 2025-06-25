from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd
from datetime import datetime

from ..exchanges.base import BaseExchange, Order, Position, OrderSide, OrderType

class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"

@dataclass
class TradingSignal:
    symbol: str
    signal_type: SignalType
    price: float
    amount: float
    confidence: float
    timestamp: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: int = 1
    metadata: Dict[str, Any] = None

@dataclass
class MarketData:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class BaseStrategy(ABC):
    def __init__(self, name: str, parameters: Dict[str, Any] = None):
        self.name = name
        self.parameters = parameters or {}
        self.positions: Dict[str, Position] = {}
        self.market_data: Dict[str, List[MarketData]] = {}
        self.signals: List[TradingSignal] = []
        
    @abstractmethod
    def analyze(self, symbol: str, market_data: List[MarketData]) -> TradingSignal:
        pass
    
    @abstractmethod
    def get_required_timeframes(self) -> List[str]:
        pass
    
    @abstractmethod
    def get_required_indicators(self) -> List[str]:
        pass
    
    def add_market_data(self, symbol: str, data: List[MarketData]):
        if symbol not in self.market_data:
            self.market_data[symbol] = []
        self.market_data[symbol].extend(data)
        
        # Keep only last 1000 candles to manage memory
        if len(self.market_data[symbol]) > 1000:
            self.market_data[symbol] = self.market_data[symbol][-1000:]
    
    def get_market_data(self, symbol: str, limit: Optional[int] = None) -> List[MarketData]:
        data = self.market_data.get(symbol, [])
        if limit:
            return data[-limit:]
        return data
    
    def update_position(self, symbol: str, position: Position):
        self.positions[symbol] = position
    
    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)
    
    def add_signal(self, signal: TradingSignal):
        self.signals.append(signal)
    
    def get_recent_signals(self, symbol: str = None, limit: int = 10) -> List[TradingSignal]:
        if symbol:
            signals = [s for s in self.signals if s.symbol == symbol]
        else:
            signals = self.signals
        return signals[-limit:]
    
    def calculate_position_size(self, signal: TradingSignal, account_balance: float, 
                              risk_per_trade: float = 0.02) -> float:
        if signal.stop_loss and signal.price != signal.stop_loss:
            risk_amount = account_balance * risk_per_trade
            price_diff = abs(signal.price - signal.stop_loss)
            risk_per_unit = price_diff / signal.price
            
            if risk_per_unit > 0:
                position_size = risk_amount / (signal.price * risk_per_unit)
                return min(position_size, signal.amount)
        
        return signal.amount
    
    def should_enter_position(self, signal: TradingSignal) -> bool:
        if signal.confidence < 0.5:
            return False
        
        current_position = self.get_position(signal.symbol)
        if current_position and current_position.size > 0:
            if (signal.signal_type == SignalType.BUY and current_position.side == "long") or \
               (signal.signal_type == SignalType.SELL and current_position.side == "short"):
                return False
        
        return True
    
    def should_exit_position(self, signal: TradingSignal) -> bool:
        current_position = self.get_position(signal.symbol)
        if not current_position or current_position.size == 0:
            return False
        
        if signal.signal_type == SignalType.CLOSE_LONG and current_position.side == "long":
            return True
        elif signal.signal_type == SignalType.CLOSE_SHORT and current_position.side == "short":
            return True
        
        return False