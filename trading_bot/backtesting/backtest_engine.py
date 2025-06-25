import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
from loguru import logger

from ..strategies.base import BaseStrategy, TradingSignal, SignalType, MarketData
from ..exchanges.base import Order, Position, OrderSide, OrderType, OrderStatus

@dataclass
class BacktestResult:
    initial_balance: float
    final_balance: float
    total_return: float
    total_return_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    start_date: datetime
    end_date: datetime
    duration_days: int
    trades: List[Dict]
    equity_curve: List[Tuple[datetime, float]]

class BacktestEngine:
    def __init__(self, initial_balance: float = 10000.0, commission: float = 0.001):
        self.initial_balance = initial_balance
        self.commission = commission
        self.reset()
    
    def reset(self):
        self.balance = self.initial_balance
        self.positions: Dict[str, Position] = {}
        self.open_orders: Dict[str, Order] = {}
        self.closed_trades: List[Dict] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.current_timestamp = None
        self.peak_balance = self.initial_balance
        self.max_drawdown = 0.0
        
    def run_backtest(self, strategy: BaseStrategy, market_data: Dict[str, List[MarketData]], 
                    start_date: datetime, end_date: datetime) -> BacktestResult:
        logger.info(f"Starting backtest for {strategy.name} from {start_date} to {end_date}")
        
        self.reset()
        
        # Filter market data by date range
        filtered_data = {}
        for symbol, data in market_data.items():
            filtered_data[symbol] = [
                d for d in data 
                if start_date <= d.timestamp <= end_date
            ]
        
        if not any(filtered_data.values()):
            raise ValueError("No market data found in the specified date range")
        
        # Get all unique timestamps and sort them
        all_timestamps = set()
        for data_list in filtered_data.values():
            all_timestamps.update(d.timestamp for d in data_list)
        
        sorted_timestamps = sorted(all_timestamps)
        
        # Process each timestamp
        for timestamp in sorted_timestamps:
            self.current_timestamp = timestamp
            
            # Update market data for strategy
            for symbol, data_list in filtered_data.items():
                current_data = [d for d in data_list if d.timestamp <= timestamp]
                if current_data:
                    strategy.add_market_data(symbol, current_data[-100:])  # Keep last 100 candles
            
            # Process signals for each symbol
            for symbol in filtered_data.keys():
                symbol_data = strategy.get_market_data(symbol, 100)
                if len(symbol_data) < 20:  # Need minimum data for analysis
                    continue
                
                # Update current positions in strategy
                if symbol in self.positions:
                    strategy.update_position(symbol, self.positions[symbol])
                
                # Get trading signal
                signal = strategy.analyze(symbol, symbol_data)
                
                if signal.signal_type != SignalType.HOLD:
                    self._process_signal(signal, symbol_data[-1])
            
            # Update equity curve
            current_equity = self._calculate_total_equity(filtered_data)
            self.equity_curve.append((timestamp, current_equity))
            
            # Update drawdown
            if current_equity > self.peak_balance:
                self.peak_balance = current_equity
            else:
                drawdown = self.peak_balance - current_equity
                if drawdown > self.max_drawdown:
                    self.max_drawdown = drawdown
        
        return self._generate_result(start_date, end_date)
    
    def _process_signal(self, signal: TradingSignal, current_market_data: MarketData):
        if signal.signal_type in [SignalType.BUY, SignalType.SELL]:
            self._open_position(signal, current_market_data)
        elif signal.signal_type in [SignalType.CLOSE_LONG, SignalType.CLOSE_SHORT]:
            self._close_position(signal, current_market_data)
    
    def _open_position(self, signal: TradingSignal, market_data: MarketData):
        # Check if we have enough balance
        position_value = signal.amount * signal.price
        commission_cost = position_value * self.commission
        total_cost = position_value + commission_cost
        
        if signal.signal_type == SignalType.BUY and total_cost > self.balance:
            logger.warning(f"Insufficient balance for BUY order: {total_cost} > {self.balance}")
            return
        
        # Calculate actual position size based on available balance
        if signal.signal_type == SignalType.BUY:
            max_position_value = self.balance * 0.95  # Use 95% of balance
            actual_amount = min(signal.amount, max_position_value / signal.price)
        else:
            actual_amount = signal.amount
        
        # Create position
        side = "long" if signal.signal_type == SignalType.BUY else "short"
        position = Position(
            symbol=signal.symbol,
            side=side,
            size=actual_amount,
            entry_price=signal.price,
            unrealized_pnl=0.0,
            percentage=0.0,
            leverage=signal.leverage
        )
        
        # Update balance
        if signal.signal_type == SignalType.BUY:
            self.balance -= (actual_amount * signal.price + actual_amount * signal.price * self.commission)
        
        self.positions[signal.symbol] = position
        
        logger.debug(f"Opened {side} position: {signal.symbol} {actual_amount} @ {signal.price}")
    
    def _close_position(self, signal: TradingSignal, market_data: MarketData):
        if signal.symbol not in self.positions:
            return
        
        position = self.positions[signal.symbol]
        exit_price = signal.price
        
        # Calculate P&L
        if position.side == "long":
            pnl = (exit_price - position.entry_price) * position.size
        else:
            pnl = (position.entry_price - exit_price) * position.size
        
        # Account for commission
        commission_cost = position.size * exit_price * self.commission
        net_pnl = pnl - commission_cost
        
        # Update balance
        if position.side == "long":
            self.balance += position.size * exit_price - commission_cost
        else:
            self.balance += net_pnl
        
        # Record trade
        trade = {
            'symbol': signal.symbol,
            'side': position.side,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'size': position.size,
            'entry_time': self.current_timestamp,
            'exit_time': self.current_timestamp,
            'pnl': net_pnl,
            'return_pct': (net_pnl / (position.size * position.entry_price)) * 100
        }
        self.closed_trades.append(trade)
        
        # Remove position
        del self.positions[signal.symbol]
        
        logger.debug(f"Closed {position.side} position: {signal.symbol} P&L: {net_pnl:.2f}")
    
    def _calculate_total_equity(self, market_data: Dict[str, List[MarketData]]) -> float:
        total_equity = self.balance
        
        for symbol, position in self.positions.items():
            if symbol in market_data and market_data[symbol]:
                current_price = market_data[symbol][-1].close
                
                if position.side == "long":
                    position_value = position.size * current_price
                    unrealized_pnl = (current_price - position.entry_price) * position.size
                else:
                    position_value = position.size * position.entry_price
                    unrealized_pnl = (position.entry_price - current_price) * position.size
                
                total_equity += unrealized_pnl
        
        return total_equity
    
    def _generate_result(self, start_date: datetime, end_date: datetime) -> BacktestResult:
        final_balance = self.equity_curve[-1][1] if self.equity_curve else self.balance
        
        # Calculate returns
        total_return = final_balance - self.initial_balance
        total_return_pct = (total_return / self.initial_balance) * 100
        
        # Calculate drawdown percentage
        max_drawdown_pct = (self.max_drawdown / self.peak_balance) * 100 if self.peak_balance > 0 else 0
        
        # Calculate trade statistics
        winning_trades = len([t for t in self.closed_trades if t['pnl'] > 0])
        losing_trades = len([t for t in self.closed_trades if t['pnl'] < 0])
        total_trades = len(self.closed_trades)
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Calculate average win/loss
        wins = [t['pnl'] for t in self.closed_trades if t['pnl'] > 0]
        losses = [t['pnl'] for t in self.closed_trades if t['pnl'] < 0]
        
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean([abs(l) for l in losses]) if losses else 0
        
        # Profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = sum([abs(l) for l in losses]) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Sharpe ratio (simplified)
        if len(self.equity_curve) > 1:
            returns = []
            for i in range(1, len(self.equity_curve)):
                ret = (self.equity_curve[i][1] - self.equity_curve[i-1][1]) / self.equity_curve[i-1][1]
                returns.append(ret)
            
            if returns and np.std(returns) > 0:
                sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)  # Annualized
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
        
        duration_days = (end_date - start_date).days
        
        return BacktestResult(
            initial_balance=self.initial_balance,
            final_balance=final_balance,
            total_return=total_return,
            total_return_pct=total_return_pct,
            max_drawdown=self.max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            start_date=start_date,
            end_date=end_date,
            duration_days=duration_days,
            trades=self.closed_trades,
            equity_curve=self.equity_curve
        )