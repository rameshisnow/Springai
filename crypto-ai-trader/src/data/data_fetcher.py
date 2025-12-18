"""
Data fetcher module - Retrieves market data from multiple sources
"""
import asyncio
import aiohttp
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import requests
from src.utils.logger import logger
from src.config.settings import config
from src.config.constants import (
    MIN_TRADING_VOLUME_USD, 
    MIN_MARKET_CAP_USD,
    EXCLUDED_COINS,
    QUOTE_ASSET,
)


class BinanceDataFetcher:
    """Fetch market data from Binance API"""
    
    BASE_URL = "https://api.binance.com/api/v3"
    TEST_NET_URL = "https://testnet.binance.vision/api/v3"
    
    def __init__(self):
        self.base_url = self.TEST_NET_URL if config.BINANCE_TESTNET else self.BASE_URL
        self.api_key = config.BINANCE_API_KEY
        self.api_secret = config.BINANCE_API_SECRET
        self.session = None
    
    async def get_all_trading_pairs(self) -> List[str]:
        """Get all available trading pairs on Binance"""
        try:
            url = f"{self.base_url}/exchangeInfo"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = [
                            s['symbol'] for s in data['symbols']
                            if s['symbol'].endswith(QUOTE_ASSET) and s['status'] == 'TRADING'
                        ]
                        logger.info(f"Found {len(pairs)} trading pairs")
                        return pairs
        except Exception as e:
            logger.error(f"Error fetching trading pairs: {e}")
        return []
    
    async def get_24h_ticker(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict]:
        """
        Get 24h ticker data for symbols
        
        Args:
            symbols: List of trading symbols (e.g., ['BTCUSDT', 'ETHUSDT'])
        
        Returns:
            Dictionary of symbol -> ticker data
        """
        if symbols is None:
            symbols = await self.get_all_trading_pairs()
        
        results = {}
        
        try:
            url = f"{self.base_url}/ticker/24hr"
            async with aiohttp.ClientSession() as session:
                tasks = []
                for symbol in symbols:
                    task = self._fetch_ticker(session, url, symbol)
                    tasks.append(task)
                
                ticker_data = await asyncio.gather(*tasks, return_exceptions=True)
                
                for symbol, data in zip(symbols, ticker_data):
                    if isinstance(data, dict):
                        results[symbol] = data
        
        except Exception as e:
            logger.error(f"Error fetching 24h ticker: {e}")
        
        return results
    
    async def _fetch_ticker(self, session, url: str, symbol: str):
        """Fetch single ticker with error handling"""
        try:
            async with session.get(f"{url}?symbol={symbol}", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.debug(f"Error fetching ticker for {symbol}: {e}")
        return None
    
    async def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100, start_time: Optional[int] = None, end_time: Optional[int] = None) -> pd.DataFrame:
        """
        Get klines (candlestick) data
        
        Args:
            symbol: Trading pair symbol
            interval: Time interval ('1h', '4h', '1d', etc.)
            limit: Number of candles to fetch (max 1000)
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)
        
        Returns:
            DataFrame with OHLCV data
        """
        try:
            url = f"{self.base_url}/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit,
            }
            
            if start_time:
                params['startTime'] = start_time
            if end_time:
                params['endTime'] = end_time
            
            # Add API key header for authenticated requests (higher rate limits)
            headers = {}
            if self.api_key:
                headers['X-MBX-APIKEY'] = self.api_key
            
            # SSL context for corporate firewalls
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Convert to DataFrame
                        df = pd.DataFrame(data, columns=[
                            'open_time', 'open', 'high', 'low', 'close', 'volume',
                            'close_time', 'quote_asset_volume', 'number_of_trades',
                            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                        ])
                        
                        # Convert to numeric
                        for col in ['open', 'high', 'low', 'close', 'volume']:
                            df[col] = pd.to_numeric(df[col])
                        
                        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
                        
                        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        except Exception as e:
            logger.error(f"Error fetching klines for {symbol}: {e}")
        
        return pd.DataFrame()
    
    async def get_order_book(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        """Get order book depth data"""
        try:
            url = f"{self.base_url}/depth"
            params = {'symbol': symbol, 'limit': limit}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.json()
        
        except Exception as e:
            logger.error(f"Error fetching order book for {symbol}: {e}")
        
        return {}
    
    async def get_account_balance(self) -> Dict[str, float]:
        """Get current account balance - requires API key"""
        # Note: This requires authenticated endpoint
        # Implementation depends on Binance API wrapper in trading module
        pass

class NewsDataFetcher:
    """Fetch cryptocurrency news"""
    
    BASE_URL = "https://newsapi.org/v2"
    
    def __init__(self):
        self.api_key = config.NEWS_API_KEY
    
    async def get_crypto_news(self, query: str = "cryptocurrency", limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch latest crypto news"""
        if not self.api_key:
            logger.warning("NewsAPI key not configured")
            return []
        
        try:
            url = f"{self.BASE_URL}/everything"
            params = {
                'q': query,
                'sortBy': 'publishedAt',
                'language': 'en',
                'pageSize': limit,
                'apiKey': self.api_key,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('articles', [])
        
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
        
        return []
    
    async def get_coin_news(self, coin_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch news for specific coin"""
        return await self.get_crypto_news(query=coin_name, limit=limit)


class DataProcessor:
    """Process and filter market data"""
    
    @staticmethod
    async def get_top_n_coins_by_volume(n: int = 10) -> List[Dict[str, Any]]:
        """
        Get top N coins by 24h volume from Binance (high liquidity)
        
        Args:
            n: Number of top coins to return
        
        Returns:
            List of top N coins sorted by 24h volume
        """
        try:
            # Get all USDT pairs from Binance
            url = f"{binance_fetcher.base_url}/ticker/24hr"
            
            # Create SSL context that doesn't verify certificates (for corporate firewalls)
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        logger.error(f"Binance API error: {resp.status}")
                        return []
                    
                    all_tickers = await resp.json()
            
            # Filter USDT pairs only
            usdt_pairs = []
            for ticker in all_tickers:
                symbol = ticker.get('symbol', '')
                if not symbol.endswith('USDT'):
                    continue
                
                # Skip excluded coins
                base_symbol = symbol.replace('USDT', '')
                if base_symbol in EXCLUDED_COINS:
                    continue
                
                # Get volume in USD (quoteVolume is already in USDT)
                volume_24h = float(ticker.get('quoteVolume', 0))
                
                # Filter by minimum volume
                if volume_24h < MIN_TRADING_VOLUME_USD:
                    continue
                
                usdt_pairs.append({
                    'symbol': base_symbol,
                    'binance_symbol': symbol,
                    'current_price': float(ticker.get('lastPrice', 0)),
                    'total_volume': volume_24h,
                    'price_change_24h': float(ticker.get('priceChange', 0)),
                    'price_change_percent_24h': float(ticker.get('priceChangePercent', 0)),
                })
            
            # Sort by 24h volume descending
            sorted_coins = sorted(
                usdt_pairs,
                key=lambda x: x['total_volume'],
                reverse=True
            )
            
            top_n = sorted_coins[:n]
            logger.info(f"Selected top {n} coins by volume: {[c['symbol'] for c in top_n]}")
            
            return top_n
        
        except Exception as e:
            logger.error(f"Error getting top N coins from Binance: {e}")
            return []
    
    @staticmethod
    def calculate_volatility(df: pd.DataFrame, window: int = 24) -> float:
        """Calculate price volatility"""
        if len(df) < window:
            return 0.0
        
        returns = df['close'].pct_change()
        volatility = returns.std() * (100 ** 0.5)  # Annualize
        return volatility
    
    @staticmethod
    def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate basic technical indicators"""
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # Moving Averages
        df['SMA20'] = df['close'].rolling(window=20).mean()
        df['SMA50'] = df['close'].rolling(window=50).mean()
        
        return df
    
    @staticmethod
    def format_ohlcv_for_prompt(df: pd.DataFrame, last_n: int = 10) -> str:
        """
        Format OHLCV data as a readable table for AI prompt
        
        Args:
            df: DataFrame with OHLCV data
            last_n: Number of recent candles to include
        
        Returns:
            Formatted string table
        """
        try:
            recent = df.tail(last_n)
            
            lines = ["Time                | Open       | High       | Low        | Close      | Volume"]
            lines.append("-" * 90)
            
            for _, row in recent.iterrows():
                time_str = row['timestamp'].strftime('%Y-%m-%d %H:%M') if 'timestamp' in row else 'N/A'
                lines.append(
                    f"{time_str:19s} | {row['open']:10.6f} | {row['high']:10.6f} | "
                    f"{row['low']:10.6f} | {row['close']:10.6f} | {row['volume']:10.0f}"
                )
            
            return "\n".join(lines)
        
        except Exception as e:
            logger.error(f"Error formatting OHLCV: {e}")
            return "No OHLCV data available"


# Singleton instances
binance_fetcher = BinanceDataFetcher()
news_fetcher = NewsDataFetcher()
data_processor = DataProcessor()
