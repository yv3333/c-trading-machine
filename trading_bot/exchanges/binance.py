import ccxt
from typing import Dict, List, Optional
from .base import BaseExchange, Balance, Order, Position, Ticker, OrderType, OrderSide, OrderStatus
import asyncio
from loguru import logger

class BinanceExchange(BaseExchange):
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        super().__init__(api_key, api_secret, testnet)
        
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'sandbox': testnet,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future' if testnet else 'spot',
            }
        })
    
    async def get_balance(self) -> List[Balance]:
        try:
            balance_data = await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.fetch_balance
            )
            
            balances = []
            for symbol, data in balance_data.items():
                if isinstance(data, dict) and 'free' in data:
                    balances.append(Balance(
                        symbol=symbol,
                        free=float(data['free']),
                        used=float(data['used']),
                        total=float(data['total'])
                    ))
            
            return balances
        except Exception as e:
            logger.error(f"Error fetching balance from Binance: {e}")
            raise
    
    async def get_ticker(self, symbol: str) -> Ticker:
        try:
            ticker_data = await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.fetch_ticker, symbol
            )
            
            return Ticker(
                symbol=symbol,
                price=float(ticker_data['last']),
                volume=float(ticker_data['baseVolume']),
                change=float(ticker_data['percentage']),
                timestamp=int(ticker_data['timestamp'])
            )
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol} from Binance: {e}")
            raise
    
    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType, 
                          amount: float, price: Optional[float] = None) -> Order:
        try:
            order_params = {
                'symbol': symbol,
                'type': order_type.value,
                'side': side.value,
                'amount': amount
            }
            
            if price is not None:
                order_params['price'] = price
            
            order_data = await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.create_order, **order_params
            )
            
            return Order(
                id=str(order_data['id']),
                symbol=symbol,
                side=side,
                type=order_type,
                amount=amount,
                price=price,
                status=OrderStatus(order_data['status']),
                timestamp=int(order_data['timestamp']),
                filled=float(order_data['filled']),
                remaining=float(order_data['remaining'])
            )
        except Exception as e:
            logger.error(f"Error creating order on Binance: {e}")
            raise
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.cancel_order, order_id, symbol
            )
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id} on Binance: {e}")
            return False
    
    async def get_order(self, order_id: str, symbol: str) -> Order:
        try:
            order_data = await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.fetch_order, order_id, symbol
            )
            
            return Order(
                id=str(order_data['id']),
                symbol=symbol,
                side=OrderSide(order_data['side']),
                type=OrderType(order_data['type']),
                amount=float(order_data['amount']),
                price=float(order_data['price']) if order_data['price'] else None,
                status=OrderStatus(order_data['status']),
                timestamp=int(order_data['timestamp']),
                filled=float(order_data['filled']),
                remaining=float(order_data['remaining'])
            )
        except Exception as e:
            logger.error(f"Error fetching order {order_id} from Binance: {e}")
            raise
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        try:
            orders_data = await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.fetch_open_orders, symbol
            )
            
            orders = []
            for order_data in orders_data:
                orders.append(Order(
                    id=str(order_data['id']),
                    symbol=order_data['symbol'],
                    side=OrderSide(order_data['side']),
                    type=OrderType(order_data['type']),
                    amount=float(order_data['amount']),
                    price=float(order_data['price']) if order_data['price'] else None,
                    status=OrderStatus(order_data['status']),
                    timestamp=int(order_data['timestamp']),
                    filled=float(order_data['filled']),
                    remaining=float(order_data['remaining'])
                ))
            
            return orders
        except Exception as e:
            logger.error(f"Error fetching open orders from Binance: {e}")
            raise
    
    async def get_positions(self) -> List[Position]:
        try:
            positions_data = await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.fetch_positions
            )
            
            positions = []
            for pos_data in positions_data:
                if float(pos_data['contracts']) > 0:
                    positions.append(Position(
                        symbol=pos_data['symbol'],
                        side=pos_data['side'],
                        size=float(pos_data['contracts']),
                        entry_price=float(pos_data['entryPrice']),
                        unrealized_pnl=float(pos_data['unrealizedPnl']),
                        percentage=float(pos_data['percentage']),
                        leverage=int(pos_data['leverage'])
                    ))
            
            return positions
        except Exception as e:
            logger.error(f"Error fetching positions from Binance: {e}")
            raise
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.set_leverage, leverage, symbol
            )
            return True
        except Exception as e:
            logger.error(f"Error setting leverage for {symbol} on Binance: {e}")
            return False
    
    async def create_stop_loss_order(self, symbol: str, side: OrderSide, 
                                   amount: float, stop_price: float) -> Order:
        try:
            order_data = await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.create_order, symbol, 'stop_market', side.value, amount, None, None, {
                    'stopPrice': stop_price
                }
            )
            
            return Order(
                id=str(order_data['id']),
                symbol=symbol,
                side=side,
                type=OrderType.STOP_LOSS,
                amount=amount,
                price=stop_price,
                status=OrderStatus(order_data['status']),
                timestamp=int(order_data['timestamp']),
                filled=float(order_data['filled']),
                remaining=float(order_data['remaining'])
            )
        except Exception as e:
            logger.error(f"Error creating stop loss order on Binance: {e}")
            raise
    
    async def create_take_profit_order(self, symbol: str, side: OrderSide, 
                                     amount: float, price: float) -> Order:
        try:
            order_data = await asyncio.get_event_loop().run_in_executor(
                None, self.exchange.create_order, symbol, 'take_profit_market', side.value, amount, None, None, {
                    'stopPrice': price
                }
            )
            
            return Order(
                id=str(order_data['id']),
                symbol=symbol,
                side=side,
                type=OrderType.TAKE_PROFIT,
                amount=amount,
                price=price,
                status=OrderStatus(order_data['status']),
                timestamp=int(order_data['timestamp']),
                filled=float(order_data['filled']),
                remaining=float(order_data['remaining'])
            )
        except Exception as e:
            logger.error(f"Error creating take profit order on Binance: {e}")
            raise