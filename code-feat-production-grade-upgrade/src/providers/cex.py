import asyncio
import random
import time
import logging
import pandas as pd
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# --- Mock CCXT.PRO Implementation ---
# This block defines mock classes for ccxt.pro, allowing for development
# and testing without a licensed copy of the library.

class MockExchange:
    """Mocks a single ccxt.pro exchange connection."""
    def __init__(self, *args, **kwargs):
        """Accept any args to be robust, ignore them."""
        try:
            self._historical_data = pd.read_csv('mock_btc_usdt_daily.csv')
            self._data_index = 0
        except FileNotFoundError:
            self._historical_data = None
            logger.warning("Mock historical data file not found. Falling back to random data.")
        self._last_price = 50000 + random.uniform(-100, 100)


    async def watch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Simulates waiting for and receiving a single ticker update."""
        await asyncio.sleep(random.uniform(0.1, 0.5)) # Simulate network latency

        if self._historical_data is not None and symbol == 'BTC/USDT':
            if self._data_index >= len(self._historical_data):
                self._data_index = 0 # Loop back

            record = self._historical_data.iloc[self._data_index]
            self._data_index += 1

            price = record['close']

            return {
                'symbol': symbol,
                'timestamp': int(record['unix']),
                'datetime': record['date'],
                'high': record['high'],
                'low': record['low'],
                'bid': price * 0.9998,
                'ask': price * 1.0002,
                'last': price,
                'baseVolume': record['Volume BTC'],
                'info': {}, # Keep the structure consistent
            }

        # Fallback to random data for other symbols or if file not found
        self._last_price *= random.uniform(0.999, 1.001)
        bid = self._last_price * 0.9998
        ask = self._last_price * 1.0002
        return {
            'symbol': symbol,
            'timestamp': int(time.time() * 1000),
            'datetime': time.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            'high': self._last_price * 1.02,
            'low': self._last_price * 0.98,
            'bid': bid,
            'ask': ask,
            'last': self._last_price,
            'baseVolume': random.uniform(1000, 5000),
            'info': {}, # Keep the structure consistent
        }

    async def watch_order_book(self, symbol: str, limit: int = 25) -> Dict[str, List]:
        """Simulates waiting for and receiving a single order book update."""
        await asyncio.sleep(random.uniform(0.1, 0.5))

        price = self._last_price
        if self._historical_data is not None and symbol == 'BTC/USDT':
            # Use the last price from the historical data if available
            # Note: self._data_index might be ahead, so we use the previous index
            current_index = self._data_index - 1 if self._data_index > 0 else 0
            if current_index < len(self._historical_data):
                price = self._historical_data.iloc[current_index]['close']

        bids = sorted([[price - random.uniform(0, 10), random.uniform(0.1, 5)] for _ in range(limit)], key=lambda x: x[0], reverse=True)
        asks = sorted([[price + random.uniform(0, 10), random.uniform(0.1, 5)] for _ in range(limit)], key=lambda x: x[0])
        return {
            'bids': bids,
            'asks': asks,
            'symbol': symbol,
            'timestamp': int(time.time() * 1000),
            'datetime': time.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        }

    async def close(self):
        """Simulates closing the connection."""
        logger.info("Mock exchange connection closed.")
        await asyncio.sleep(0.01)

    def fetch_deposit_withdraw_fees(self, codes=None, params={}):
        """Simulates fetching deposit and withdrawal fees."""
        logger.info("Mock exchange: fetching deposit/withdraw fees.")
        return {
            'USDT': {
                'info': {'coin': 'USDT'},
                'networks': {
                    'deposit': {
                        'TRX': {'fee': 0.0, 'percentage': False},
                        'ERC20': {'fee': 0.0, 'percentage': False},
                        'SOL': {'fee': 0.0, 'percentage': False},
                    },
                    'withdraw': {
                        'TRX': {'fee': 1.0, 'percentage': False},
                        'ERC20': {'fee': 25.0, 'percentage': False},
                        'SOL': {'fee': 0.5, 'percentage': False},
                    }
                }
            }
        }

    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1d', limit: int = 100, params={}) -> List[List]:
        """Simulates fetching historical OHLCV data."""
        await asyncio.sleep(0.1) # Simulate network latency

        if self._historical_data is not None and symbol == 'BTC/USDT' and timeframe == '1d':
            # Use the mock CSV data for BTC/USDT daily
            df = self._historical_data.copy()
            # Ensure the timestamp is in the integer ms format ccxt expects
            df['unix'] = df['unix'].astype(int)
            # Select the required columns in the correct order
            ohlcv = df[['unix', 'open', 'high', 'low', 'close', 'Volume BTC']].values.tolist()
            # Return the last `limit` records
            return ohlcv[-limit:]

        # Fallback for other symbols/timeframes: generate random data
        ohlcv_data = []
        # Use milliseconds for timestamp
        timestamp = int(time.time() * 1000) - limit * 86400000 # Start `limit` days ago
        price = 50000
        for _ in range(limit):
            open_price = price * random.uniform(0.99, 1.01)
            high_price = open_price * random.uniform(1.0, 1.02)
            low_price = open_price * random.uniform(0.98, 1.0)
            close_price = random.uniform(low_price, high_price)
            volume = random.uniform(100, 1000)
            ohlcv_data.append([timestamp, open_price, high_price, low_price, close_price, volume])
            price = close_price
            timestamp += 86400000 # Add one day in milliseconds
        return ohlcv_data

class MockCCXTPro:
    """Mocks the ccxtpro library by dynamically creating MockExchange instances."""
    def __getattr__(self, name: str):
        # Return a constructor for a MockExchange
        return MockExchange

# --- Library Import ---
# This block attempts to import the real ccxt.pro library. If it fails,
# it logs a warning and prepares to use the mock implementation.
try:
    import ccxt.pro as ccxtpro
    IS_MOCK = False
except ImportError:
    logger.warning("ccxt.pro not found. Using a mock implementation for CEXProvider.")
    IS_MOCK = True
    ccxtpro = MockCCXTPro()

# --- Real CEX Provider ---
from .base import BaseProvider

class CEXProvider(BaseProvider):
    """
    Connects to Centralized Exchanges (CEX) using ccxt.pro (or a mock version)
    to get real-time data via WebSockets.
    """
    def __init__(self, name: str, config: Dict = None, force_mock: bool = False):
        super().__init__(name)
        self.exchange_id = name.lower()
        self.is_mock = force_mock or IS_MOCK  # Use mock if forced or if library is missing

        if self.is_mock:
            # When mocking, we know the class is MockExchange, so we instantiate it.
            self.exchange = MockExchange()
            return

        # --- The following code runs only if using the REAL ccxt.pro library ---
        try:
            exchange_class = getattr(ccxtpro, self.exchange_id)
            api_keys = config.get('api_keys', {}).get(self.exchange_id, {})
            # Use empty dict for public endpoints if no keys are provided
            self.exchange = exchange_class(api_keys if api_keys else {})
        except (AttributeError, TypeError) as e:
            # Re-raise with a more informative message
            raise ValueError(f"Exchange '{self.exchange_id}' is not supported by ccxt.pro or API config is invalid. Error: {e}")

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches the next ticker data update from the WebSocket stream.
        The mock class has its own simulated latency, so no special handling is needed.
        """
        return await self.exchange.watch_ticker(symbol)

    async def get_order_book(self, symbol: str, limit: int = 25) -> Dict[str, List]:
        """
        Fetches the next order book data update from the WebSocket stream.
        The mock class has its own simulated latency, so no special handling is needed.
        """
        return await self.exchange.watch_order_book(symbol, limit)

    async def close(self):
        """Closes the underlying ccxt.pro exchange connection."""
        # The mock exchange also has a 'close' method, so this works for both cases.
        await self.exchange.close()

    async def get_historical_data(self, symbol: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
        """
        Fetches historical OHLCV data, implementing a cache-first strategy.

        The method first checks for a locally cached CSV file in the `data/` directory.
        The filename is standardized based on the provider name, symbol, and timeframe
        (e.g., 'BINANCE_BTC-USDT_1d.csv').

        - If a valid cache file is found, it returns the data from the CSV.
        - If the file doesn't exist or is invalid, it fetches the data from the
          exchange API, saves it to the CSV cache for future use, and then
          returns the data.

        Args:
            symbol: The trading symbol (e.g., 'BTC/USDT').
            timeframe: The K-line timeframe (e.g., '1d', '4h').
            limit: The number of data points to retrieve.

        Returns:
            A list of dictionaries, where each dictionary represents an OHLCV candle,
            or an empty list if an error occurs.
        """
        # Sanitize inputs to create a valid filename
        safe_symbol = symbol.replace('/', '_')
        cache_filename = f"{self.name.upper()}_{safe_symbol}_{timeframe}.csv"
        # The path should be relative to the project root, where the app is run.
        cache_filepath = f"data/{cache_filename}"

        # 1. Check for a local cache first
        try:
            logger.info(f"Checking for cached data at: {cache_filepath}")
            df = pd.read_csv(cache_filepath)
            # Basic validation to see if the file seems correct
            required_cols = {'timestamp', 'open', 'high', 'low', 'close', 'volume'}
            if required_cols.issubset(df.columns):
                logger.info(f"Cache hit. Loading data from {cache_filepath}")
                # Return the last `limit` records from the cached file
                return df.tail(limit).to_dict('records')
        except FileNotFoundError:
            logger.info("Cache miss. Fetching data from exchange.")
        except Exception as e:
            logger.warning(f"Could not read cache file {cache_filepath}. Error: {e}. Refetching.")

        # 2. If no cache, fetch from the exchange
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if not ohlcv:
                logger.warning(f"Exchange returned no data for {symbol} {timeframe}.")
                return []

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

            # 3. Save the new data to the cache
            logger.info(f"Saving new data to cache: {cache_filepath}")
            df.to_csv(cache_filepath, index=False)

            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Failed to fetch or process historical data for {symbol} from {self.name}: {e}")
            return []

    async def get_transfer_fees(self, asset: str) -> Dict[str, Any]:
        """
        Fetches deposit and withdrawal fee and network information for a specific asset.
        This uses the synchronous part of the ccxt library, but is wrapped in an
        async method to be consistent with the other provider methods.
        This method works for both real and mock exchanges, as the mock exchange
        also has a 'fetch_deposit_withdraw_fees' method.
        """
        try:
            loop = asyncio.get_running_loop()
            # Use run_in_executor for the synchronous ccxt call
            all_fees = await loop.run_in_executor(
                None, self.exchange.fetch_deposit_withdraw_fees, [asset]
            )

            # Process the structured data
            if asset in all_fees and 'networks' in all_fees[asset]:
                networks = all_fees[asset]['networks']
                return {
                    'asset': asset,
                    'deposit': networks.get('deposit', {}),
                    'withdraw': networks.get('withdraw', {}),
                }
            else:
                return {'asset': asset, 'error': 'No fee info found for asset.'}

        except Exception as e:
            logger.error(f"Could not fetch transfer fees for {asset} from {self.name}: {e}")
            return {'asset': asset, 'error': str(e)}
