"""
Configuration Loader Module.

This module is responsible for loading application configuration from various
sources, such as environment variables (.env file) and YAML files.
It is designed to be completely independent of the UI (Streamlit),
raising well-defined errors instead of displaying UI components.
This separation of concerns makes the configuration logic more robust and reusable.
"""
import os
import yaml
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

class ConfigError(Exception):
    """Custom exception for configuration loading errors."""
    pass

def load_yaml_config(filepath: str) -> dict:
    """
    Loads a YAML file and returns its content.
    Raises ConfigError if the file is not found or cannot be parsed.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f"Configuration file not found: {filepath}")
    except Exception as e:
        raise ConfigError(f"Error loading YAML configuration from {filepath}: {e}")

def load_app_config() -> dict:
    """
    Loads configuration from environment variables and YAML files.
    This function is UI-agnostic and raises exceptions on failure.
    """
    config = {}

    # --- Database Configuration ---
    config['db_dsn'] = os.getenv("DB_DSN")

    # --- RPC URLs for DEX Providers ---
    config['rpc_urls'] = {
        "ethereum": os.getenv("RPC_URL_ETHEREUM", "https://eth.llamarpc.com"),
        "polygon": os.getenv("RPC_URL_POLYGON", "https://polygon-rpc.com/"),
    }

    # --- API Keys for CEX Providers ---
    config['api_keys'] = {
        "binance": {
            "apiKey": os.getenv("BINANCE_API_KEY", ""),
            "secret": os.getenv("BINANCE_API_SECRET", ""),
        },
        "coinbase": {
            "apiKey": os.getenv("COINBASE_API_KEY", ""),
            "secret": os.getenv("COINBASE_API_SECRET", ""),
        }
    }

    # --- Arbitrage Engine Settings ---
    # Note: Paths are relative to the project root where the app is run.
    fee_config = load_yaml_config('config/fees.yml')
    config['arbitrage'] = {
        'threshold': 0.2,
        'fees': fee_config,
        'default_symbols': {
            'bridge': 'BTC.BTC/ETH.ETH',
            'dex': 'WETH/USDC'
        }
    }

    # --- Qualitative Data ---
    config['qualitative_data'] = load_yaml_config('config/qualitative_data.yml')

    return config
