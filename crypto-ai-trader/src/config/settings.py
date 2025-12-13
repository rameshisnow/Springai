"""
Configuration settings for Crypto AI Trader
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)


class Config:
    """Base configuration"""
    
    # API Configuration
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
    BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "False").lower().strip() == "true"
    
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "free")
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
    
    # Trading Configuration
    STARTING_CAPITAL_AUD = float(os.getenv("STARTING_CAPITAL_AUD", "1000"))
    TARGET_PROFIT_PERCENT = float(os.getenv("TARGET_PROFIT_PERCENT", "20"))
    RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", "2"))
    
    # System Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
    BACKTEST_MODE = os.getenv("BACKTEST_MODE", "False").lower() == "true"
    
    # Server Configuration
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")  # Listen on all interfaces for mobile access
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8080"))
    
    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./crypto_trader.db")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Data directories
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    LOG_DIR = os.path.join(BASE_DIR, "logs")
    DATA_DIR = os.path.join(BASE_DIR, "data")
    
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        errors = []
        
        if not cls.BINANCE_API_KEY:
            errors.append("BINANCE_API_KEY not set")
        if not cls.BINANCE_API_SECRET:
            errors.append("BINANCE_API_SECRET not set")
        if not cls.CLAUDE_API_KEY and not cls.OPENAI_API_KEY:
            errors.append("Either CLAUDE_API_KEY or OPENAI_API_KEY must be set")
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN not set")
        if not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID not set")
        
        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(errors))
        
        return True


class DevelopmentConfig(Config):
    """Development configuration"""
    BINANCE_TESTNET = True
    ENVIRONMENT = "development"
    LOG_LEVEL = "DEBUG"


class TestingConfig(Config):
    """Testing configuration"""
    BINANCE_TESTNET = True
    BACKTEST_MODE = True
    LOG_LEVEL = "DEBUG"
    DATABASE_URL = "sqlite:///:memory:"


class ProductionConfig(Config):
    """Production configuration"""
    # Read from environment variable, don't hardcode
    BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "False").lower().strip() == "true"
    ENVIRONMENT = "production"
    LOG_LEVEL = "INFO"


def get_config():
    """Get appropriate config based on environment"""
    env = os.getenv("ENVIRONMENT", "production")
    
    if env == "development":
        return DevelopmentConfig()
    elif env == "testing":
        return TestingConfig()
    else:
        return ProductionConfig()


# Export config instance
config = get_config()
