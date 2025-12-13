"""
Technical indicators module - compute RSI, EMA, ATR, momentum, volume spike
"""
import pandas as pd
import numpy as np
from typing import Dict, Any
from src.utils.logger import logger


def compute_rsi(df: pd.DataFrame, period: int = 14, column: str = 'close') -> pd.Series:
    """
    Compute Relative Strength Index (RSI)
    
    Args:
        df: DataFrame with OHLCV data
        period: RSI period (default 14)
        column: Price column to use
    
    Returns:
        Series with RSI values (0-100)
    """
    try:
        delta = df[column].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    except Exception as e:
        logger.error(f"Error computing RSI: {e}")
        return pd.Series([50] * len(df))


def compute_ema(df: pd.DataFrame, period: int = 20, column: str = 'close') -> pd.Series:
    """
    Compute Exponential Moving Average (EMA)
    
    Args:
        df: DataFrame with OHLCV data
        period: EMA period
        column: Price column to use
    
    Returns:
        Series with EMA values
    """
    try:
        return df[column].ewm(span=period, adjust=False).mean()
    except Exception as e:
        logger.error(f"Error computing EMA: {e}")
        return df[column]


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Compute Average True Range (ATR) - volatility indicator
    
    Args:
        df: DataFrame with OHLCV data (needs high, low, close)
        period: ATR period (default 14)
    
    Returns:
        Series with ATR values
    """
    try:
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr
    except Exception as e:
        logger.error(f"Error computing ATR: {e}")
        return pd.Series([0] * len(df))


def compute_momentum(df: pd.DataFrame, period: int = 10, column: str = 'close') -> pd.Series:
    """
    Compute Momentum - rate of price change
    
    Args:
        df: DataFrame with OHLCV data
        period: Lookback period
        column: Price column to use
    
    Returns:
        Series with momentum values (percent change)
    """
    try:
        momentum = ((df[column] - df[column].shift(period)) / df[column].shift(period)) * 100
        return momentum
    except Exception as e:
        logger.error(f"Error computing momentum: {e}")
        return pd.Series([0] * len(df))


def compute_volume_spike(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Compute volume spike ratio - current volume vs average volume
    
    Args:
        df: DataFrame with OHLCV data
        period: Lookback period for average
    
    Returns:
        Series with volume spike ratios (1.0 = average, >1.0 = higher than average)
    """
    try:
        avg_volume = df['volume'].rolling(window=period).mean()
        volume_ratio = df['volume'] / avg_volume
        return volume_ratio
    except Exception as e:
        logger.error(f"Error computing volume spike: {e}")
        return pd.Series([1.0] * len(df))


def compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, column: str = 'close') -> Dict[str, pd.Series]:
    """
    Compute MACD (Moving Average Convergence Divergence)
    
    Args:
        df: DataFrame with OHLCV data
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line period
        column: Price column to use
    
    Returns:
        Dictionary with 'macd', 'signal', and 'histogram' Series
    """
    try:
        ema_fast = df[column].ewm(span=fast, adjust=False).mean()
        ema_slow = df[column].ewm(span=slow, adjust=False).mean()
        
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        
        return {
            'macd': macd,
            'signal': signal_line,
            'histogram': histogram
        }
    except Exception as e:
        logger.error(f"Error computing MACD: {e}")
        return {
            'macd': pd.Series([0] * len(df)),
            'signal': pd.Series([0] * len(df)),
            'histogram': pd.Series([0] * len(df))
        }


def compute_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, column: str = 'close') -> Dict[str, pd.Series]:
    """
    Compute Bollinger Bands
    
    Args:
        df: DataFrame with OHLCV data
        period: Moving average period
        std_dev: Number of standard deviations
        column: Price column to use
    
    Returns:
        Dictionary with 'upper', 'middle', and 'lower' Series
    """
    try:
        middle = df[column].rolling(window=period).mean()
        std = df[column].rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }
    except Exception as e:
        logger.error(f"Error computing Bollinger Bands: {e}")
        return {
            'upper': df[column],
            'middle': df[column],
            'lower': df[column]
        }


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all technical indicators and add them to the DataFrame
    
    Args:
        df: DataFrame with OHLCV data (requires: open, high, low, close, volume)
    
    Returns:
        DataFrame with added indicator columns
    """
    try:
        df = df.copy()
        
        # RSI
        df['rsi'] = compute_rsi(df, period=14)
        
        # EMAs (include short-term 9/21 for crossover logic)
        df['ema_9'] = compute_ema(df, period=9)
        df['ema_21'] = compute_ema(df, period=21)
        df['ema_20'] = compute_ema(df, period=20)
        df['ema_50'] = compute_ema(df, period=50)
        df['ema_200'] = compute_ema(df, period=200)
        
        # ATR
        df['atr'] = compute_atr(df, period=14)
        
        # Momentum
        df['momentum'] = compute_momentum(df, period=10)
        
        # Volume spike
        df['volume_spike'] = compute_volume_spike(df, period=20)
        
        # MACD
        macd_data = compute_macd(df)
        df['macd'] = macd_data['macd']
        df['macd_signal'] = macd_data['signal']
        df['macd_histogram'] = macd_data['histogram']
        
        # Bollinger Bands
        bb_data = compute_bollinger_bands(df)
        df['bb_upper'] = bb_data['upper']
        df['bb_middle'] = bb_data['middle']
        df['bb_lower'] = bb_data['lower']
        
        # Trend detection
        df['trend'] = 'neutral'
        df.loc[df['ema_20'] > df['ema_50'], 'trend'] = 'uptrend'
        df.loc[df['ema_20'] < df['ema_50'], 'trend'] = 'downtrend'
        
        logger.debug(f"Computed indicators for {len(df)} candles")
        return df
    
    except Exception as e:
        logger.error(f"Error computing all indicators: {e}")
        return df


def format_indicators_for_prompt(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Format indicators into a dict suitable for AI prompt
    
    Args:
        df: DataFrame with computed indicators
    
    Returns:
        Dictionary with latest indicator values
    """
    try:
        latest = df.iloc[-1]
        
        return {
            'rsi': round(latest.get('rsi', 50), 2),
            'ema_20': round(latest.get('ema_20', latest.get('close', 0)), 6),
            'ema_50': round(latest.get('ema_50', latest.get('close', 0)), 6),
            'ema_200': round(latest.get('ema_200', latest.get('close', 0)), 6),
            'atr': round(latest.get('atr', 0), 6),
            'momentum': round(latest.get('momentum', 0), 2),
            'volume_spike': round(latest.get('volume_spike', 1.0), 2),
            'macd': round(latest.get('macd', 0), 6),
            'macd_signal': round(latest.get('macd_signal', 0), 6),
            'macd_histogram': round(latest.get('macd_histogram', 0), 6),
            'trend': latest.get('trend', 'neutral'),
            'bb_position': _get_bb_position(latest),
        }
    except Exception as e:
        logger.error(f"Error formatting indicators: {e}")
        return {}


def _get_bb_position(row: pd.Series) -> str:
    """Helper to determine price position relative to Bollinger Bands"""
    try:
        close = row.get('close', 0)
        upper = row.get('bb_upper', close)
        lower = row.get('bb_lower', close)
        middle = row.get('bb_middle', close)
        
        if close >= upper:
            return 'overbought'
        elif close <= lower:
            return 'oversold'
        elif close > middle:
            return 'above_middle'
        else:
            return 'below_middle'
    except:
        return 'neutral'
