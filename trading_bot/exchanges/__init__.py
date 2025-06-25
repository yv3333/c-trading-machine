from .base import BaseExchange, OrderType, OrderSide, OrderStatus, Balance, Order, Position, Ticker
from .binance import BinanceExchange
from .okx import OKXExchange
from .bybit import BybitExchange

__all__ = [
    'BaseExchange', 'OrderType', 'OrderSide', 'OrderStatus', 
    'Balance', 'Order', 'Position', 'Ticker',
    'BinanceExchange', 'OKXExchange', 'BybitExchange'
]

def create_exchange(exchange_name: str, api_key: str, api_secret: str, testnet: bool = True) -> BaseExchange:
    exchanges = {
        'binance': BinanceExchange,
        'okx': OKXExchange,
        'bybit': BybitExchange
    }
    
    if exchange_name.lower() not in exchanges:
        raise ValueError(f"Unsupported exchange: {exchange_name}")
    
    return exchanges[exchange_name.lower()](api_key, api_secret, testnet)