import streamlit as st
import asyncio
import nest_asyncio
import time
import logging

# --- Basic Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from .config import load_config
from .db import DatabaseManager
from .engine import ArbitrageEngine
from .providers.cex import CEXProvider
from .providers.dex import DEXProvider
from .providers.bridge import BridgeProvider
from .ui.tabs import show_realtime_tab, show_depth_tab, show_arbitrage_tab, show_history_tab, show_kline_tab, show_api_guide_tab, show_comprehensive_arbitrage_tab
from .ui.components import sidebar_controls

# Apply nest_asyncio to allow running asyncio event loops within Streamlit's loop
# This is crucial for integrating async libraries with Streamlit
nest_asyncio.apply()

st.set_page_config(
    page_title="数字货币交易所对比工具 (生产级)",
    layout="wide",
    page_icon="🚀",
    initial_sidebar_state="expanded"
)

# --- App Title ---
st.markdown("<h1>🚀 数字货币交易所对比工具 (生产级)</h1>", unsafe_allow_html=True)

# --- Demo Mode Information ---
if st.session_state.get('demo_mode', True):
    st.info(
        """📊 **演示模式已启用** - 您正在查看模拟数据和功能展示。\n\n
        🔍 **可用功能：**\n
        • 实时行情监控（模拟数据）\n
        • 市场深度分析\n
        • 套利机会识别\n
        • 交易费用对比\n
        • 交易所定性分析\n\n
        💡 **提示：** 要使用真实数据，请在左侧边栏配置API密钥。
        """,
        icon="ℹ️"
    )

# --- Initialization & Caching ---

@st.cache_data
def get_config():
    """Load configuration from file and cache it."""
    return load_config()

@st.cache_resource
def get_db_manager(dsn):
    """Create and cache the database manager and its connection pool."""
    if not dsn:
        st.warning("数据库DSN未配置，历史分析功能将被禁用。")
        return None
    try:
        db_manager = DatabaseManager(dsn)
        # nest_asyncio.apply() at the top of the file handles event loop integration.
        # A simple asyncio.run() should be sufficient and robust here.
        asyncio.run(db_manager.connect())
        asyncio.run(db_manager.init_db())
        return db_manager
    except OSError as e:
        if "getaddrinfo failed" in str(e):
            st.error(
                "**数据库连接失败：无法解析主机名。**\n\n"
                "这通常意味着您正在本地运行此应用，但数据库连接字符串 (`DB_DSN`) "
                "指向的是Docker内部主机 (`db`)。\n\n"
                "**解决方案：**\n"
                "1. 打开项目根目录下的 `.env` 文件。\n"
                "2. 注释掉为Docker准备的行：\n"
                "   ```\n"
                "   # DB_DSN=postgresql://user:password@db:5432/crypto_data\n"
                "   ```\n"
                "3. 取消注释为本地运行准备的行：\n"
                "   ```\n"
                "   DB_DSN=postgresql://user:password@localhost:5432/crypto_data\n"
                "   ```\n"
                "4. 重新启动Streamlit应用。",
                icon="🚨"
            )
        else:
            st.error(f"连接数据库时发生操作系统错误: {e}")
        return None
    except Exception as e:
        st.error(f"连接数据库时发生未知错误: {e}")
        return None

@st.cache_resource
def get_providers(_config, _session_state):
    """
    Create and cache a list of all data providers based on the current mode (Demo or Real).
    This function is made resilient to individual provider failures.
    """
    providers = []
    is_demo_mode = _session_state.get('demo_mode', True)

    # Prepare a unified config for providers, prioritizing UI keys over file-based keys
    provider_config = _config.copy()
    file_keys = _config.get('api_keys', {})
    ui_keys = _session_state.get('api_keys', {})
    merged_keys = {**file_keys, **ui_keys}
    provider_config['api_keys'] = merged_keys

    # CEX Providers
    for ex_id in _session_state.selected_exchanges:
        try:
            # Pass the merged config and the demo mode flag to the provider
            providers.append(CEXProvider(name=ex_id, config=provider_config, force_mock=is_demo_mode))
        except Exception as e:
            st.warning(f"初始化中心化交易所 (CEX) 提供商 '{ex_id}' 失败: {e}", icon="⚠️")

    if is_demo_mode:
        st.info("演示模式下禁用去中心化交易所 (DEX) 和跨链桥提供商。", icon="ℹ️")
    else:
        # DEX Providers (only initialize in real data mode)
        try:
            if _config.get('rpc_urls', {}).get('ethereum'):
                providers.append(DEXProvider(name="Uniswap V3", rpc_url=_config['rpc_urls']['ethereum']))
            else:
                st.warning("以太坊 RPC URL 未配置，去中心化交易所 (DEX) 提供商已禁用。", icon="⚠️")
        except Exception as e:
            st.warning(f"初始化去中心化交易所 (DEX) 提供商 'Uniswap V3' 失败: {e}", icon="⚠️")

        # Bridge Providers (only initialize in real data mode)
        try:
            providers.append(BridgeProvider(name="Thorchain"))
        except Exception as e:
            st.warning(f"初始化跨链桥提供商 'Thorchain' 失败: {e}", icon="⚠️")

    return providers

def init_session_state(config):
    """Initializes the session state with default values from the config."""
    default_symbols = config.get('arbitrage', {}).get('default_symbols', {})
    # Remove bridge_symbol initialization to avoid conflict with text_input widget
    if 'dex_symbol' not in st.session_state:
        st.session_state.dex_symbol = default_symbols.get('dex', 'WETH/USDC')
    if 'api_keys' not in st.session_state:
        st.session_state.api_keys = {}
    if 'selected_exchanges' not in st.session_state:
        st.session_state.selected_exchanges = ['binance', 'okx', 'bybit']

# --- Main App Logic ---
def main():
    config = get_config()
    init_session_state(config)

    # The sidebar must be rendered first to initialize all its widgets and session state keys
    sidebar_controls()

    # Initialize managers
    db_manager = get_db_manager(config.get("db_dsn"))

    # Get providers based on current selection in session state
    # Pass session_state explicitly because it's used as part of the cache key for get_providers
    providers = get_providers(config, st.session_state)

    # Initialize arbitrage engine
    arbitrage_engine = ArbitrageEngine(providers, config.get('arbitrage', {}))

    # Main content area with tabs
    cex_providers = [p for p in providers if isinstance(p, CEXProvider)]

    if st.session_state.get('demo_mode', True):
        tab_names = ["🎯 功能指南", "实时行情", "市场深度", "📈 K线图", "套利机会", "综合套利分析", "费用对比", "交易所对比", "历史分析", "API 指南"]
        tabs = st.tabs(tab_names)
        tab_map = {name: tab for name, tab in zip(tab_names, tabs)}
        
        with tab_map["🎯 功能指南"]:
            from .ui.demo_guide import show_demo_guide, show_feature_highlights
            show_demo_guide()
            show_feature_highlights()
    else:
        tab_names = ["实时行情", "市场深度", "📈 K线图", "套利机会", "综合套利分析", "费用对比", "交易所对比", "历史分析", "API 指南"]
        tabs = st.tabs(tab_names)
        tab_map = {name: tab for name, tab in zip(tab_names, tabs)}

    with tab_map["实时行情"]:
        show_realtime_tab(providers, db_manager)

    with tab_map["市场深度"]:
        show_depth_tab(cex_providers)

    with tab_map["📈 K线图"]:
        show_kline_tab(cex_providers)

    with tab_map["套利机会"]:
        show_arbitrage_tab(arbitrage_engine)

    with tab_map["综合套利分析"]:
        show_comprehensive_arbitrage_tab(arbitrage_engine)

    with tab_map["费用对比"]:
        from .ui.tabs import show_fees_tab
        show_fees_tab(cex_providers)

    with tab_map["交易所对比"]:
        from .ui.tabs import show_comparison_tab
        show_comparison_tab(config.get('qualitative_data', {}))

    with tab_map["历史分析"]:
        show_history_tab(db_manager)

    with tab_map["API 指南"]:
        show_api_guide_tab()


if __name__ == "__main__":
    main()

    # --- Auto-refresh loop ---
    if st.session_state.get('auto_refresh_enabled', False):
        interval = st.session_state.get('auto_refresh_interval', 10)
        time.sleep(interval)
        st.rerun()
