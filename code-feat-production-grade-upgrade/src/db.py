import aiosqlite
import asyncio
import os
from typing import List, Dict, Any
from datetime import datetime
import pandas as pd

class DatabaseManager:
    """
    Manages the connection to a SQLite database and handles all data
    storage and retrieval operations asynchronously using aiosqlite.
    """
    def __init__(self, db_path: str):
        if not db_path:
            raise ValueError("Database path is required.")
        self.db_path = db_path
        # Ensure the directory for the database file exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = None

    async def connect(self):
        """Establishes a connection to the SQLite database file."""
        try:
            self.conn = await aiosqlite.connect(self.db_path)
            # Use Row factory to allow accessing columns by name
            self.conn.row_factory = aiosqlite.Row
            print(f"Successfully connected to SQLite database at {self.db_path}")
        except Exception as e:
            print(f"Error: Could not connect to the SQLite database. {e}")
            self.conn = None
            raise

    async def close(self):
        """Closes the database connection."""
        if self.conn:
            await self.conn.close()
            print("SQLite database connection closed.")

    async def init_db(self):
        """
        Initializes the database by creating the necessary tables and indexes.
        This method is idempotent.
        """
        if not self.conn:
            raise ConnectionError("Database is not connected. Call connect() first.")

        async with self.conn.cursor() as cursor:
            # Create the main table for ticker data with SQLite-compatible types
            await cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticker_data (
                timestamp TEXT NOT NULL,
                provider_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL,
                bid REAL,
                ask REAL,
                volume REAL
            );
            """)
            # Create an index for faster queries on timestamp
            await cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_ticker_data_timestamp ON ticker_data (timestamp DESC);"
            )
        await self.conn.commit()
        print("Database initialization complete.")

    async def save_ticker_data(self, data: List[Dict[str, Any]]):
        """
        Saves a batch of ticker data records to the database using executemany.

        Args:
            data: A list of dictionaries, where each dict represents a ticker record.
        """
        if not self.conn:
            raise ConnectionError("Database is not connected.")
        if not data:
            return

        records_to_insert = []
        for row in data:
            # Convert datetime objects to ISO 8601 string format for SQLite
            ts = row.get('timestamp', datetime.utcnow())
            if isinstance(ts, datetime):
                ts = ts.isoformat()

            records_to_insert.append((
                ts,
                row.get('provider_name'),
                row.get('symbol'),
                row.get('price'),
                row.get('bid'),
                row.get('ask'),
                row.get('volume')
            ))

        try:
            await self.conn.executemany(
                "INSERT INTO ticker_data (timestamp, provider_name, symbol, price, bid, ask, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
                records_to_insert
            )
            await self.conn.commit()
            print(f"Successfully saved {len(records_to_insert)} records to the database.")
        except Exception as e:
            print(f"Error saving data to SQLite database: {e}")

    async def query_historical_data(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> pd.DataFrame:
        """
        Queries historical data for a given symbol and time range.

        Returns:
            A pandas DataFrame containing the queried data.
        """
        if not self.conn:
            raise ConnectionError("Database is not connected.")

        # Convert datetime objects to ISO 8601 strings for comparison
        start_str = start_time.isoformat()
        end_str = end_time.isoformat()

        query = """
        SELECT * FROM ticker_data
        WHERE symbol = ? AND timestamp BETWEEN ? AND ?
        ORDER BY timestamp ASC;
        """
        async with self.conn.execute(query, (symbol, start_str, end_str)) as cursor:
            records = await cursor.fetchall()

        if not records:
            return pd.DataFrame()

        # Convert list of row objects to a list of dicts, then to DataFrame
        return pd.DataFrame([dict(row) for row in records])
