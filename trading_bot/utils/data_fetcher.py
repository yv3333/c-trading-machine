import ccxt
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import asyncio
from loguru import logger

from ..strategies.base import MarketData
from ..exchanges.base import BaseExchange

class DataFetcher:
    def __init__(self, exchange: BaseExchange):
        self.exchange = exchange
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', 
                         limit: int = 500, since: Optional[datetime] = None) -> List[MarketData]:
        try:
            # Convert datetime to timestamp if provided
            since_timestamp = None
            if since:
                since_timestamp = int(since.timestamp() * 1000)
            
            # Fetch OHLCV data using ccxt
            if hasattr(self.exchange, 'exchange') and hasattr(self.exchange.exchange, 'fetch_ohlcv'):
                ohlcv_data = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    self.exchange.exchange.fetch_ohlcv,
                    symbol, timeframe, since_timestamp, limit
                )
            else:
                raise NotImplementedError("Exchange does not support OHLCV data fetching")
            
            # Convert to MarketData objects
            market_data = []
            for candle in ohlcv_data:
                timestamp, open_price, high, low, close, volume = candle
                market_data.append(MarketData(
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(timestamp / 1000),
                    open=float(open_price),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    volume=float(volume)
                ))
            
            return market_data
        
        except Exception as e:
            logger.error(f"Error fetching OHLCV data for {symbol}: {e}")
            raise
    
    async def fetch_historical_data(self, symbol: str, timeframe: str = '1h',
                                  start_date: datetime = None, 
                                  end_date: datetime = None) -> List[MarketData]:
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()
        
        all_data = []
        current_date = start_date
        
        # Fetch data in chunks to avoid rate limits
        while current_date < end_date:
            try:
                chunk_data = await self.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=1000,
                    since=current_date
                )
                
                if not chunk_data:
                    break
                
                # Filter data within date range
                filtered_data = [
                    data for data in chunk_data
                    if start_date <= data.timestamp <= end_date
                ]
                
                all_data.extend(filtered_data)
                
                # Update current_date for next iteration
                if chunk_data:
                    current_date = chunk_data[-1].timestamp + timedelta(hours=1)
                else:
                    break
                
                # Add delay to respect rate limits
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error fetching chunk starting from {current_date}: {e}")
                break
        
        # Remove duplicates and sort by timestamp
        unique_data = {}
        for data in all_data:
            key = (data.symbol, data.timestamp)
            if key not in unique_data:
                unique_data[key] = data
        
        sorted_data = sorted(unique_data.values(), key=lambda x: x.timestamp)
        
        logger.info(f"Fetched {len(sorted_data)} candles for {symbol} from {start_date} to {end_date}")
        return sorted_data
    
    async def fetch_multiple_symbols(self, symbols: List[str], timeframe: str = '1h',
                                   start_date: datetime = None,
                                   end_date: datetime = None) -> Dict[str, List[MarketData]]:
        
        result = {}
        
        # Fetch data for each symbol concurrently with semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent requests
        
        async def fetch_symbol_data(symbol: str):
            async with semaphore:
                try:
                    data = await self.fetch_historical_data(
                        symbol=symbol,
                        timeframe=timeframe,
                        start_date=start_date,
                        end_date=end_date
                    )
                    return symbol, data
                except Exception as e:
                    logger.error(f"Failed to fetch data for {symbol}: {e}")
                    return symbol, []
        
        # Create tasks for all symbols
        tasks = [fetch_symbol_data(symbol) for symbol in symbols]
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result_item in results:
            if isinstance(result_item, Exception):
                logger.error(f"Task failed with exception: {result_item}")
                continue
                
            symbol, data = result_item
            result[symbol] = data
        
        return result
    
    def convert_to_dataframe(self, market_data: List[MarketData]) -> pd.DataFrame:
        data_dict = {
            'timestamp': [data.timestamp for data in market_data],
            'open': [data.open for data in market_data],
            'high': [data.high for data in market_data],
            'low': [data.low for data in market_data],
            'close': [data.close for data in market_data],
            'volume': [data.volume for data in market_data]
        }
        
        df = pd.DataFrame(data_dict)
        df.set_index('timestamp', inplace=True)
        return df
    
    @staticmethod
    def save_to_csv(market_data: List[MarketData], filename: str):
        df = DataFetcher.convert_to_dataframe(market_data)
        df.to_csv(filename)
        logger.info(f"Saved {len(market_data)} records to {filename}")
    
    @staticmethod
    def load_from_csv(filename: str, symbol: str) -> List[MarketData]:
        try:
            df = pd.read_csv(filename, index_col='timestamp', parse_dates=True)
            
            market_data = []
            for timestamp, row in df.iterrows():
                market_data.append(MarketData(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume'])
                ))
            
            logger.info(f"Loaded {len(market_data)} records from {filename}")
            return market_data
            
        except Exception as e:
            logger.error(f"Error loading data from {filename}: {e}")
            raise