from .base import BaseStrategy, TradingSignal, SignalType, MarketData
from .ma_crossover import MACrossoverStrategy
from .rsi_strategy import RSIStrategy

__all__ = [
    'BaseStrategy', 'TradingSignal', 'SignalType', 'MarketData',
    'MACrossoverStrategy', 'RSIStrategy'
]

def get_strategy(strategy_name: str, **kwargs) -> BaseStrategy:
    strategies = {
        'ma_crossover': MACrossoverStrategy,
        'rsi': RSIStrategy,
    }
    
    if strategy_name.lower() not in strategies:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    
    return strategies[strategy_name.lower()](**kwargs)