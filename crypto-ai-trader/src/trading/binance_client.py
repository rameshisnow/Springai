"""
Binance REST client built on the official connector for order management and account operations.
"""
from typing import Dict, List, Optional, Any

from binance.spot import Spot

from src.utils.logger import binance_logger
from src.config.settings import config


class BinanceClient:
    """Official Binance connector spot client."""

    def __init__(self):
        base_url = "https://testnet.binance.vision" if config.BINANCE_TESTNET else "https://api.binance.com"
        self.client = Spot(api_key=config.BINANCE_API_KEY, api_secret=config.BINANCE_API_SECRET, base_url=base_url)
        binance_logger.info(f"Initialized Binance Spot client (Testnet: {config.BINANCE_TESTNET})")

    def get_account_balance(self) -> Dict[str, float]:
        """Return available balances as asset -> free amount."""
        try:
            information = self.client.account()
            balances = {
                asset["asset"]: float(asset["free"])
                for asset in information["balances"]
                if float(asset["free"]) > 0
            }

            binance_logger.info(f"Retrieved {len(balances)} non-zero balances")
            return balances
        except Exception as exc:
            binance_logger.error(f"Error fetching account balance: {exc}")
            return {}

    def get_asset_balance(self, asset: str) -> float:
        """Return free balance for a single asset."""
        try:
            balances = self.get_account_balance()
            return balances.get(asset, 0.0)
        except Exception as exc:
            binance_logger.error(f"Error fetching asset balance for {asset}: {exc}")
            return 0.0

    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Return exchange info for a symbol."""
        try:
            info = self.client.exchange_info(symbol=symbol)
            symbols = info.get("symbols", [])
            return symbols[0] if symbols else {}
        except Exception as exc:
            binance_logger.error(f"Error fetching symbol info for {symbol}: {exc}")
            return {}

    def get_current_price(self, symbol: str) -> float:
        """Get the latest price for a symbol."""
        try:
            ticker = self.client.ticker_price(symbol=symbol)
            return float(ticker.get("price", 0.0))
        except Exception as exc:
            binance_logger.error(f"Error fetching price for {symbol}: {exc}")
            return 0.0

    def get_order_book(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        """Fetch order book depth."""
        try:
            return self.client.depth(symbol=symbol, limit=limit)
        except Exception as exc:
            binance_logger.error(f"Error fetching order book for {symbol}: {exc}")
            return {}

    def _format_quantity(self, symbol: str, quantity: float) -> str:
        """Format quantity to match symbol's precision and step size requirements"""
        # Get symbol info to find the correct step size
        symbol_info = self.get_symbol_info(symbol)
        if symbol_info:
            filters = symbol_info.get('filters', [])
            for f in filters:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f.get('stepSize', 0.001))
                    # Round to the step size
                    if step_size > 0:
                        # Round down to nearest step size to be safe
                        rounded = int(quantity / step_size) * step_size
                    else:
                        rounded = round(quantity, 8)
                    # Convert to string and remove trailing zeros
                    formatted = f"{rounded:.8f}".rstrip('0').rstrip('.')
                    return formatted
        
        # Fallback: round to 8 decimals maximum and remove trailing zeros
        rounded = round(quantity, 8)
        formatted = f"{rounded:.8f}".rstrip('0').rstrip('.')
        return formatted

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """Place a spot market order."""
        try:
            # Format quantity correctly for the symbol
            formatted_qty = self._format_quantity(symbol, quantity)
            binance_logger.info(f"🔍 DEBUG: Placing order - Symbol: {symbol}, Raw qty: {quantity}, Formatted: {formatted_qty}")
            
            response = self.client.new_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=formatted_qty,
            )
            binance_logger.info(f"Market order placed: {symbol} {side} {quantity}")
            return response
        except Exception as exc:
            binance_logger.error(f"Market order failed for {symbol}: {exc}")
            return {}

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        """Place a limit order."""
        try:
            formatted_qty = self._format_quantity(symbol, quantity)
            formatted_price = f"{price:.8f}".rstrip('0').rstrip('.')
            
            response = self.client.new_order(
                symbol=symbol,
                side=side,
                type="LIMIT",
                timeInForce=time_in_force,
                quantity=formatted_qty,
                price=formatted_price,
            )
            binance_logger.info(f"Limit order placed: {symbol} {side} @ {price}")
            return response
        except Exception as exc:
            binance_logger.error(f"Limit order failed for {symbol}: {exc}")
            return {}

    def place_stop_loss_order(self, symbol: str, side: str, quantity: float, stop_price: float) -> Dict[str, Any]:
        """Place a stop loss limit order."""
        try:
            formatted_qty = self._format_quantity(symbol, quantity)
            formatted_stop = f"{stop_price:.8f}".rstrip('0').rstrip('.')
            formatted_price = f"{stop_price * 0.995:.8f}".rstrip('0').rstrip('.')
            
            response = self.client.new_order(
                symbol=symbol,
                side=side,
                type="STOP_LOSS_LIMIT",
                timeInForce="GTC",
                quantity=formatted_qty,
                price=formatted_price,
                stopPrice=formatted_stop,
            )
            binance_logger.info(f"Stop loss order placed: {symbol} {side} @ {stop_price}")
            return response
        except Exception as exc:
            binance_logger.error(f"Stop loss order failed for {symbol}: {exc}")
            return {}

    def place_take_profit_order(self, symbol: str, side: str, quantity: float, stop_price: float) -> Dict[str, Any]:
        """Place a take profit limit order."""
        try:
            formatted_qty = self._format_quantity(symbol, quantity)
            formatted_stop = f"{stop_price:.8f}".rstrip('0').rstrip('.')
            formatted_price = f"{stop_price * 1.005:.8f}".rstrip('0').rstrip('.')
            
            response = self.client.new_order(
                symbol=symbol,
                side=side,
                type="TAKE_PROFIT_LIMIT",
                timeInForce="GTC",
                quantity=formatted_qty,
                price=formatted_price,
                stopPrice=formatted_stop,
            )
            binance_logger.info(f"Take profit placed: {symbol} {side} @ {stop_price}")
            return response
        except Exception as exc:
            binance_logger.error(f"Take profit order failed for {symbol}: {exc}")
            return {}

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an open order."""
        try:
            return self.client.cancel_order(symbol=symbol, orderId=order_id)
        except Exception as exc:
            binance_logger.error(f"Cancel failed for {symbol} {order_id}: {exc}")
            return {}

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Retrieve a single order."""
        try:
            return self.client.get_order(symbol=symbol, orderId=order_id)
        except Exception as exc:
            binance_logger.error(f"Unable to fetch order {order_id}: {exc}")
            return {}

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return open orders, optionally filtered by symbol."""
        try:
            if symbol:
                return self.client.get_open_orders(symbol=symbol)
            return self.client.get_open_orders()
        except Exception as exc:
            binance_logger.error(f"Failed to list open orders: {exc}")
            return []

    def get_order_history(
        self,
        symbol: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch historical orders."""
        try:
            params = {
                "symbol": symbol,
                "limit": limit,
            }
            if start_time:
                params["startTime"] = start_time
            if end_time:
                params["endTime"] = end_time

            return self.client.get_all_orders(**params)
        except Exception as exc:
            binance_logger.error(f"Error fetching order history for {symbol}: {exc}")
            return []

    def get_my_trades(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch trade history."""
        try:
            return self.client.my_trades(symbol=symbol, limit=limit)
        except Exception as exc:
            binance_logger.error(f"Error fetching trades for {symbol}: {exc}")
            return []

    def calculate_order_quantity(self, symbol: str, quote_amount: float) -> float:
        """Derive quantity from quote amount using latest price and lot size limits."""
        try:
            current_price = self.get_current_price(symbol)
            if current_price <= 0 or quote_amount <= 0:
                return 0.0

            quantity = quote_amount / current_price
            symbol_info = self.get_symbol_info(symbol)
            if not symbol_info:
                return round(quantity, 6)

            filters = symbol_info.get("filters", [])
            for filter_item in filters:
                if filter_item.get("filterType") == "LOT_SIZE":
                    step = float(filter_item.get("stepSize", "0.00000001"))
                    precision = max(0, len(str(step).split(".")[-1].rstrip("0")))
                    return round(quantity, precision)

            return quantity
        except Exception as exc:
            binance_logger.error(f"Error calculating quantity for {symbol}: {exc}")
            return 0.0

    def test_connectivity(self) -> bool:
        """Verify REST connectivity with Binance."""
        try:
            self.client.ping()
            binance_logger.info("Binance connectivity OK")
            return True
        except Exception as exc:
            binance_logger.error(f"Binance ping failed: {exc}")
            return False


binance_client = BinanceClient()
