import pandas as pd
from typing import Dict, List, Any
from datetime import datetime
import talib

from .base import BaseStrategy, TradingSignal, SignalType, MarketData

class RSIStrategy(BaseStrategy):
    def __init__(self, rsi_period: int = 14, oversold_level: int = 30, overbought_level: int = 70):
        super().__init__("RSI_Strategy", {
            "rsi_period": rsi_period,
            "oversold_level": oversold_level,
            "overbought_level": overbought_level
        })
        self.rsi_period = rsi_period
        self.oversold_level = oversold_level
        self.overbought_level = overbought_level
    
    def get_required_timeframes(self) -> List[str]:
        return ["1h", "4h"]
    
    def get_required_indicators(self) -> List[str]:
        return ["RSI", "MACD", "BOLLINGER_BANDS"]
    
    def analyze(self, symbol: str, market_data: List[MarketData]) -> TradingSignal:
        if len(market_data) < self.rsi_period + 10:
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
        
        # Calculate indicators
        df['rsi'] = talib.RSI(df['close'].values, timeperiod=self.rsi_period)
        df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'].values)
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(df['close'].values)
        
        # Get latest values
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        current_price = current['close']
        rsi_current = current['rsi']
        rsi_previous = previous['rsi']
        macd_current = current['macd']
        macd_signal_current = current['macd_signal']
        bb_upper = current['bb_upper']
        bb_lower = current['bb_lower']
        
        # Determine signal
        signal_type = SignalType.HOLD
        confidence = 0.0
        amount = 0.0
        stop_loss = None
        take_profit = None
        
        # RSI Oversold and bouncing back
        if (rsi_previous <= self.oversold_level and 
            rsi_current > self.oversold_level and
            current_price <= bb_lower * 1.02):  # Near lower Bollinger Band
            
            signal_type = SignalType.BUY
            confidence = self._calculate_confidence(df, "buy")
            amount = 1.0
            stop_loss = min(current_price * 0.97, bb_lower * 0.99)
            take_profit = current_price * 1.06
            
        # RSI Overbought and falling back
        elif (rsi_previous >= self.overbought_level and 
              rsi_current < self.overbought_level and
              current_price >= bb_upper * 0.98):  # Near upper Bollinger Band
            
            signal_type = SignalType.SELL
            confidence = self._calculate_confidence(df, "sell")
            amount = 1.0
            stop_loss = max(current_price * 1.03, bb_upper * 1.01)
            take_profit = current_price * 0.94
        
        # Divergence signals
        elif self._check_bullish_divergence(df):
            signal_type = SignalType.BUY
            confidence = self._calculate_confidence(df, "buy") * 0.8  # Lower confidence for divergence
            amount = 0.5  # Smaller position size
            stop_loss = current_price * 0.96
            take_profit = current_price * 1.08
            
        elif self._check_bearish_divergence(df):
            signal_type = SignalType.SELL
            confidence = self._calculate_confidence(df, "sell") * 0.8
            amount = 0.5
            stop_loss = current_price * 1.04
            take_profit = current_price * 0.92
        
        # Check for position exit signals
        current_position = self.get_position(symbol)
        if current_position and current_position.size > 0:
            if (current_position.side == "long" and 
                rsi_current >= self.overbought_level):
                signal_type = SignalType.CLOSE_LONG
                confidence = 0.8
                amount = current_position.size
                
            elif (current_position.side == "short" and 
                  rsi_current <= self.oversold_level):
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
                'rsi': rsi_current,
                'macd': macd_current,
                'macd_signal': macd_signal_current,
                'bb_upper': bb_upper,
                'bb_lower': bb_lower,
                'volume': current['volume']
            }
        )
    
    def _calculate_confidence(self, df: pd.DataFrame, signal_direction: str) -> float:
        confidence = 0.5
        
        current = df.iloc[-1]
        rsi = current['rsi']
        macd = current['macd']
        macd_signal = current['macd_signal']
        
        # RSI strength
        if signal_direction == "buy":
            if rsi < 35:
                confidence += 0.2
            elif rsi < 40:
                confidence += 0.1
        else:  # sell
            if rsi > 65:
                confidence += 0.2
            elif rsi > 60:
                confidence += 0.1
        
        # MACD confirmation
        if signal_direction == "buy" and macd > macd_signal:
            confidence += 0.15
        elif signal_direction == "sell" and macd < macd_signal:
            confidence += 0.15
        
        # Volume confirmation
        volume_ma = df['volume'].rolling(window=10).mean()
        if current['volume'] > volume_ma.iloc[-1] * 1.5:
            confidence += 0.1
        
        # Price action confirmation
        if signal_direction == "buy":
            recent_low = df['low'].tail(5).min()
            if current['close'] > recent_low * 1.02:
                confidence += 0.1
        else:  # sell
            recent_high = df['high'].tail(5).max()
            if current['close'] < recent_high * 0.98:
                confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _check_bullish_divergence(self, df: pd.DataFrame, lookback: int = 20) -> bool:
        if len(df) < lookback:
            return False
        
        recent_df = df.tail(lookback)
        
        # Find recent lows in price and RSI
        price_low_idx = recent_df['low'].idxmin()
        rsi_low_idx = recent_df['rsi'].idxmin()
        
        # Check if we have a potential divergence pattern
        if abs(price_low_idx - rsi_low_idx) > 5:
            return False
        
        # Price making lower low, RSI making higher low
        if len(df) > lookback + 10:
            older_df = df.iloc[-(lookback + 10):-lookback]
            old_price_low = older_df['low'].min()
            old_rsi_low = older_df['rsi'].min()
            
            current_price_low = recent_df['low'].min()
            current_rsi_low = recent_df['rsi'].min()
            
            if (current_price_low < old_price_low and 
                current_rsi_low > old_rsi_low):
                return True
        
        return False
    
    def _check_bearish_divergence(self, df: pd.DataFrame, lookback: int = 20) -> bool:
        if len(df) < lookback:
            return False
        
        recent_df = df.tail(lookback)
        
        # Find recent highs in price and RSI
        price_high_idx = recent_df['high'].idxmax()
        rsi_high_idx = recent_df['rsi'].idxmax()
        
        # Check if we have a potential divergence pattern
        if abs(price_high_idx - rsi_high_idx) > 5:
            return False
        
        # Price making higher high, RSI making lower high
        if len(df) > lookback + 10:
            older_df = df.iloc[-(lookback + 10):-lookback]
            old_price_high = older_df['high'].max()
            old_rsi_high = older_df['rsi'].max()
            
            current_price_high = recent_df['high'].max()
            current_rsi_high = recent_df['rsi'].max()
            
            if (current_price_high > old_price_high and 
                current_rsi_high < old_rsi_high):
                return True
        
        return False