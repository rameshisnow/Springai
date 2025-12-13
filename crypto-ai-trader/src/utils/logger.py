"""
Centralized logging configuration
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from src.config.settings import config

# Create logs directory if it doesn't exist
os.makedirs(config.LOG_DIR, exist_ok=True)


def setup_logger(name: str, log_file: str = None) -> logging.Logger:
    """
    Setup a logger with both file and console handlers
    
    Args:
        name: Logger name
        log_file: Optional specific log file name
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # Format
    log_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File Handler
    if log_file is None:
        log_file = f"{name.replace('.', '_')}.log"
    
    file_path = os.path.join(config.LOG_DIR, log_file)
    file_handler = RotatingFileHandler(
        file_path,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(getattr(logging, config.LOG_LEVEL))
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, config.LOG_LEVEL))
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    
    return logger


# Main application logger
logger = setup_logger("crypto_trader", "crypto_trader.log")
# Trade logger
trade_logger = setup_logger("trades", "trades.log")
# AI logger
ai_logger = setup_logger("ai_analyzer", "ai_analyzer.log")
# Risk logger
risk_logger = setup_logger("risk_manager", "risk_manager.log")
# Binance logger
binance_logger = setup_logger("binance_client", "binance_client.log")
