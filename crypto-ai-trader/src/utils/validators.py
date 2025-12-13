"""
Validation utilities
"""
from typing import List, Dict, Any
import re


def validate_coin_symbol(symbol: str) -> bool:
    """Validate Binance trading symbol format"""
    return bool(re.match(r'^[A-Z0-9]{2,10}$', symbol))


def validate_api_key(key: str) -> bool:
    """Validate API key format"""
    return len(key) > 0 and len(key) < 500


def validate_price(price: float) -> bool:
    """Validate price is positive"""
    return price > 0


def validate_quantity(quantity: float) -> bool:
    """Validate quantity is positive"""
    return quantity > 0


def validate_percentage(value: float) -> bool:
    """Validate percentage value (0-100)"""
    return 0 <= value <= 100


def validate_time_format(time_str: str) -> bool:
    """Validate time format HH:MM:SS"""
    return bool(re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$', time_str))


class ValidationError(Exception):
    """Custom validation error"""
    pass


def validate_trade_data(trade_data: Dict[str, Any]) -> bool:
    """
    Validate trade data structure
    
    Args:
        trade_data: Dictionary with trade information
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If validation fails
    """
    required_fields = ['symbol', 'side', 'quantity', 'entry_price']
    
    for field in required_fields:
        if field not in trade_data:
            raise ValidationError(f"Missing required field: {field}")
    
    if trade_data['side'] not in ['BUY', 'SELL']:
        raise ValidationError(f"Invalid side: {trade_data['side']}")
    
    if not validate_price(trade_data['entry_price']):
        raise ValidationError(f"Invalid price: {trade_data['entry_price']}")
    
    if not validate_quantity(trade_data['quantity']):
        raise ValidationError(f"Invalid quantity: {trade_data['quantity']}")
    
    return True
