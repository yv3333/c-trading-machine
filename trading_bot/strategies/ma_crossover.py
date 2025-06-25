import pandas as pd
from typing import Dict, List, Any
from datetime import datetime
import talib

from .base import BaseStrategy, TradingSignal, SignalType, MarketData

class MACrossoverStrategy(BaseStrategy):
    def __init__(self, fast_period: int = 10, slow_period: int = 20, confidence_threshold: float = 0.7):
        super().__init__("MA_Crossover", {
            "fast_period": fast_period,
            "slow_period": slow_period,
            "confidence_threshold": confidence_threshold
        })
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.confidence_threshold = confidence_threshold
    
    def get_required_timeframes(self) -> List[str]:
        return ["1h", "4h"]
    
    def get_required_indicators(self) -> List[str]:
        return ["SMA", "EMA", "RSI"]
    
    def analyze(self, symbol: str, market_data: List[MarketData]) -> TradingSignal:
        if len(market_data) < max(self.fast_period, self.slow_period) + 1:
            return TradingSignal(
                symbol=symbol,
                signal_type=SignalType.HOLD,
                price=market_data[-1].close,
                amount=0,
                confidence=0.0,
                timestamp=datetime.now()
            )
        
        # Convert to pandas DataFrame
        df = pd.DataFrame([
            {
                'timestamp': data.timestamp,
                'open': data.open,
                'high': data.high,
                'low': data.low,
                'close': data.close,
                'volume': data.volume
            } for data in market_data
        ])
        
        # Calculate moving averages
        df['fast_ma'] = talib.SMA(df['close'].values, timeperiod=self.fast_period)
        df['slow_ma'] = talib.SMA(df['close'].values, timeperiod=self.slow_period)
        df['rsi'] = talib.RSI(df['close'].values, timeperiod=14)
        
        # Get latest values
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        current_price = current['close']
        fast_ma_current = current['fast_ma']
        slow_ma_current = current['slow_ma']
        fast_ma_previous = previous['fast_ma']
        slow_ma_previous = previous['slow_ma']
        rsi = current['rsi']
        
        # Determine signal
        signal_type = SignalType.HOLD
        confidence = 0.0
        amount = 0.0
        stop_loss = None
        take_profit = None
        
        # Golden cross (fast MA crosses above slow MA)
        if (fast_ma_previous <= slow_ma_previous and 
            fast_ma_current > slow_ma_current and
            rsi < 70):  # Not overbought
            
            signal_type = SignalType.BUY
            confidence = self._calculate_confidence(df, "buy")
            amount = 1.0
            stop_loss = current_price * 0.98  # 2% stop loss
            take_profit = current_price * 1.04  # 4% take profit
            
        # Death cross (fast MA crosses below slow MA)
        elif (fast_ma_previous >= slow_ma_previous and 
              fast_ma_current < slow_ma_current and
              rsi > 30):  # Not oversold
            
            signal_type = SignalType.SELL
            confidence = self._calculate_confidence(df, "sell")
            amount = 1.0
            stop_loss = current_price * 1.02  # 2% stop loss
            take_profit = current_price * 0.96  # 4% take profit
        
        # Check for position exit signals
        current_position = self.get_position(symbol)
        if current_position and current_position.size > 0:
            if (current_position.side == "long" and 
                fast_ma_current < slow_ma_current and
                fast_ma_previous >= slow_ma_previous):
                signal_type = SignalType.CLOSE_LONG
                confidence = 0.8
                amount = current_position.size
                
            elif (current_position.side == "short" and 
                  fast_ma_current > slow_ma_current and
                  fast_ma_previous <= slow_ma_previous):
                signal_type = SignalType.CLOSE_SHORT
                confidence = 0.8
                amount = current_position.size
        
        return TradingSignal(
            symbol=symbol,
            signal_type=signal_type,
            price=current_price,
            amount=amount,
            confidence=confidence,
            timestamp=datetime.now(),
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata={
                'fast_ma': fast_ma_current,
                'slow_ma': slow_ma_current,
                'rsi': rsi,
                'volume': current['volume']
            }
        )
    
    def _calculate_confidence(self, df: pd.DataFrame, signal_direction: str) -> float:
        # Base confidence
        confidence = 0.6
        
        # Check volume confirmation
        volume_ma = df['volume'].rolling(window=20).mean()
        if df.iloc[-1]['volume'] > volume_ma.iloc[-1] * 1.2:
            confidence += 0.1
        
        # Check RSI levels
        rsi = df.iloc[-1]['rsi']
        if signal_direction == "buy" and 30 < rsi < 50:
            confidence += 0.1
        elif signal_direction == "sell" and 50 < rsi < 70:
            confidence += 0.1
        
        # Check price momentum
        price_change = (df.iloc[-1]['close'] - df.iloc[-5]['close']) / df.iloc[-5]['close']
        if signal_direction == "buy" and price_change > 0:
            confidence += 0.1
        elif signal_direction == "sell" and price_change < 0:
            confidence += 0.1
        
        return min(confidence, 1.0)