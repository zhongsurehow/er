import streamlit as st
import asyncio
import nest_asyncio
import time
import logging
import pandas as pd
import plotly.graph_objects as go
from typing import List, Dict, Any
from datetime import datetime, timedelta

# --- Basic Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Local Imports ---
from .config import load_config
from .db import DatabaseManager
from .engine import ArbitrageEngine, Opportunity
from .providers.cex import CEXProvider
from .providers.dex import DEXProvider
from .providers.bridge import BridgeProvider
from .ui.components import sidebar_controls, display_error

# Apply nest_asyncio to allow running asyncio event loops within Streamlit's loop
nest_asyncio.apply()

# --- Page Configuration ---
st.set_page_config(
    page_title="套利机会仪表板",
    layout="wide",
    page_icon="🎯",
    initial_sidebar_state="expanded"
)

# --- Helper Functions ---
def safe_run_async(coro):
    """Safely runs an async coroutine, handling nested event loops."""
    try:
        return asyncio.run(coro)
    except RuntimeError as e:
        if "cannot run loop while another loop is running" in str(e):
            # This is expected in Streamlit's environment with nest_asyncio
            return asyncio.run(coro)
        st.error(f"异步操作失败: {e}")
        return None

def _validate_symbol(symbol: str) -> bool:
    """Validates that the symbol is not empty and has a valid format."""
    if not symbol or '/' not in symbol or len(symbol.split('/')) != 2:
        st.error("请输入有效的交易对格式，例如 'BTC/USDT'。")
        return False
    return True

def _create_depth_chart(order_book: dict) -> go.Figure:
    """Creates a Plotly order book depth chart."""
    bids = pd.DataFrame(order_book.get('bids', []), columns=['price', 'volume']).astype(float)
    asks = pd.DataFrame(order_book.get('asks', []), columns=['price', 'volume']).astype(float)
    bids = bids.sort_values('price', ascending=False)
    asks = asks.sort_values('price', ascending=True)
    bids['cumulative'] = bids['volume'].cumsum()
    asks['cumulative'] = asks['volume'].cumsum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bids['price'], y=bids['cumulative'], name='买单', fill='tozeroy', line_color='green'))
    fig.add_trace(go.Scatter(x=asks['price'], y=asks['cumulative'], name='卖单', fill='tozeroy', line_color='red'))
    fig.update_layout(title_text=f"{order_book.get('symbol', '')} 市场深度", xaxis_title="价格", yaxis_title="累计数量", height=300, margin=dict(l=20, r=20, t=40, b=20))
    return fig

# --- Caching Functions ---
@st.cache_data
def get_config():
    """Load configuration from file and cache it."""
    return load_config()

@st.cache_resource
def get_db_manager(db_path: str):
    """Creates and caches the database manager."""
    if not db_path: return None
    db_manager = DatabaseManager(db_path)
    try:
        asyncio.run(db_manager.__aenter__())
        asyncio.run(db_manager.init_db())
        return db_manager
    except Exception as e:
        st.error(f"连接或初始化SQLite数据库时失败: {e}")
        asyncio.run(db_manager.__aexit__(None, None, None))
        return None

@st.cache_resource
def get_providers(_config: Dict, _session_state) -> List[BaseProvider]:
    """Create and cache a list of all data providers."""
    providers = []
    is_demo_mode = not bool(_session_state.get('api_keys'))
    provider_config = _config.copy()
    provider_config['api_keys'] = {**_config.get('api_keys', {}), **_session_state.get('api_keys', {})}
    for ex_id in _session_state.selected_exchanges:
        try:
            providers.append(CEXProvider(name=ex_id, config=provider_config, force_mock=is_demo_mode))
        except ValueError as e:
            st.error(f"初始化 CEX 提供商 '{ex_id}' 失败: {e}", icon="🚨")
        except Exception as e:
            st.warning(f"初始化 CEX 提供商 '{ex_id}' 时发生未知错误: {e}", icon="⚠️")
    return providers

def init_session_state(config):
    """Initializes the session state with default values."""
    if 'selected_exchanges' not in st.session_state:
        st.session_state.selected_exchanges = ['binance', 'okx', 'bybit']
    if 'selected_symbols' not in st.session_state:
        st.session_state.selected_symbols = ['BTC/USDT', 'ETH/USDT']
    if 'api_keys' not in st.session_state:
        st.session_state.api_keys = {}

# --- Dashboard UI ---
def show_dashboard(engine: ArbitrageEngine, providers: List[BaseProvider]):
    """The main view of the application, designed as a single, consolidated dashboard."""
    st.title("🎯 套利机会仪表板")

    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("📈 实时套利机会")
        opp_placeholder = st.empty()
        with st.spinner("正在寻找套利机会..."):
            opportunities = safe_run_async(engine.find_opportunities(st.session_state.selected_symbols))
            if not opportunities:
                opp_placeholder.success("✅ 当前未发现套利机会。")
            else:
                df = pd.DataFrame(opportunities)
                df = df.sort_values(by="profit_percentage", ascending=False)
                display_df = df[['profit_percentage', 'buy_at', 'sell_at', 'net_profit_usd', 'symbol']]
                display_df['路径'] = display_df['buy_at'] + ' → ' + display_df['sell_at']
                display_df = display_df[['profit_percentage', '路径', 'net_profit_usd', 'symbol']]
                display_df.columns = ['收益率 (%)', '路径', '净利润 (USD)', '交易对']
                opp_placeholder.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "收益率 (%)": st.column_config.NumberColumn(format="%.4f%%"),
                        "净利润 (USD)": st.column_config.NumberColumn(format="$%.4f"),
                    }
                )

    with col2:
        st.subheader("📊 价格监控")
        price_placeholder = st.empty()

        with st.spinner("正在获取最新价格..."):
            tasks = []
            cex_providers = [p for p in providers if isinstance(p, CEXProvider)]
            for symbol in st.session_state.selected_symbols:
                for provider in cex_providers:
                    tasks.append(provider.get_ticker(symbol))

            all_tickers = safe_run_async(asyncio.gather(*tasks))

            if all_tickers:
                # Filter out errors and process into a list of dicts
                processed_tickers = [
                    {'symbol': t['symbol'], 'provider': t['provider_name'], 'price': t['last']}
                    for t in all_tickers if t and 'error' not in t
                ]
                if processed_tickers:
                    price_df = pd.DataFrame(processed_tickers)
                    # Create a pivot table: symbols as rows, providers as columns, prices as values
                    pivot_df = price_df.pivot(index='symbol', columns='provider', values='price')
                    price_placeholder.dataframe(pivot_df, use_container_width=True)
                else:
                    price_placeholder.warning("未能获取任何有效的价格数据。")
            else:
                price_placeholder.warning("未能获取任何价格数据。")

    st.markdown("---")

    st.subheader("🌊 市场深度可视化")
    depth_cols = st.columns(3)
    selected_ex = depth_cols[0].selectbox("选择交易所", options=[p.name for p in providers if isinstance(p, CEXProvider)], key="depth_exchange")
    selected_sym = depth_cols[1].text_input("输入交易对", st.session_state.selected_symbols[0], key="depth_symbol")

    if depth_cols[2].button("查询深度", key="depth_button"):
        if _validate_symbol(selected_sym):
            provider = next((p for p in providers if p.name == selected_ex), None)
            if provider:
                with st.spinner(f"正在从 {provider.name} 获取 {selected_sym} 的订单簿..."):
                    order_book = safe_run_async(provider.get_order_book(selected_sym))
                    if order_book and 'error' not in order_book:
                        st.plotly_chart(_create_depth_chart(order_book), use_container_width=True)
                    else:
                        display_error(f"无法获取订单簿: {order_book.get('error', '未知错误')}")

    st.markdown("---")
    with st.expander("🏢 交易所定性对比"):
        show_comparison_view(get_config().get('qualitative_data', {}))


def show_comparison_view(qualitative_data: dict):
    """Displays a side-by-side comparison of qualitative data for selected exchanges."""
    if not qualitative_data:
        st.warning("未找到定性数据。")
        return

    key_to_chinese = {
        'security_measures': '安全措施', 'customer_service': '客户服务', 'platform_stability': '平台稳定性',
        'fund_insurance': '资金保险', 'regional_restrictions': '地区限制', 'withdrawal_limits': '提现限额',
        'withdrawal_speed': '提现速度', 'supported_cross_chain_bridges': '支持的跨链桥',
        'api_support_details': 'API支持详情', 'fee_discounts': '手续费折扣', 'margin_leverage_details': '杠杆交易详情',
        'maintenance_schedule': '维护计划', 'user_rating_summary': '用户评分摘要', 'tax_compliance_info': '税务合规信息',
        'deposit_networks': '充值网络', 'deposit_fees': '充值费用', 'withdrawal_networks': '提现网络',
        'margin_trading_api': '保证金交易API'
    }

    exchange_list = list(qualitative_data.keys())
    selected = st.multiselect(
        "选择要比较的交易所",
        options=exchange_list,
        default=exchange_list[:3] if len(exchange_list) >= 3 else exchange_list,
        format_func=lambda x: x.capitalize(),
        key="qualitative_multiselect"
    )

    if selected:
        comparison_data = {exch: qualitative_data[exch] for exch in selected if exch in qualitative_data}
        df = pd.DataFrame(comparison_data).rename(index=key_to_chinese)
        all_keys_df = pd.DataFrame(index=list(key_to_chinese.values()))
        df_display = all_keys_df.join(df).fillna("N/A")
        st.dataframe(df_display, use_container_width=True)

    with st.expander("🪙 资产转账分析"):
        show_asset_transfer_view(providers)


def show_asset_transfer_view(cex_providers: List[CEXProvider]):
    """Displays a side-by-side comparison of transfer fees for a given asset."""
    asset = st.text_input("输入要比较的资产代码", "USDT", key="transfer_asset_input").upper()

    if st.button("比较资产转账选项", key="compare_transfers"):
        if not asset:
            st.error("请输入一个资产代码。")
            return

        with st.spinner(f"正在从所有选定的交易所获取 {asset} 的转账费用..."):
            results = safe_run_async(asyncio.gather(*[p.get_transfer_fees(asset) for p in cex_providers]))

        all_networks = set()
        processed_data = {}
        failed_providers = []

        for i, res in enumerate(results):
            provider_name = cex_providers[i].name.capitalize()
            if isinstance(res, dict) and 'error' not in res:
                withdraw_info = res.get('withdraw', {})
                processed_data[provider_name] = {}
                for network, details in withdraw_info.items():
                    all_networks.add(network)
                    fee = details.get('fee')
                    processed_data[provider_name][network] = f"{fee:.6f}".rstrip('0').rstrip('.') if fee is not None else "N/A"
            else:
                failed_providers.append(provider_name)

        if failed_providers:
            st.warning(f"无法获取以下交易所的费用数据: {', '.join(failed_providers)}。")

        if processed_data:
            df = pd.DataFrame(processed_data).reindex(sorted(list(all_networks))).fillna("不支持")
            st.subheader(f"{asset} 提现费用对比")
            st.dataframe(df, use_container_width=True)
        else:
            st.warning(f"未能成功获取任何交易所关于 '{asset}' 的费用数据。")

    with st.expander("📈 K线图与历史数据"):
        show_kline_view(providers)


def show_kline_view(providers: List[BaseProvider]):
    """Displays a candlestick chart for a selected symbol and exchange."""
    cex_providers = [p for p in providers if isinstance(p, CEXProvider)]
    if not cex_providers:
        st.warning("无可用CEX提供商。")
        return

    col1, col2, col3, col4 = st.columns(4)
    name = col1.selectbox("选择交易所", options=[p.name for p in cex_providers], key="kline_exchange")
    symbol = col2.text_input("输入交易对", "BTC/USDT", key="kline_symbol")
    timeframe = col3.selectbox("选择时间周期", options=['1d', '4h', '1h', '30m', '5m'], key="kline_timeframe")
    limit = col4.number_input("数据点", min_value=20, value=100, key="kline_limit")

    if st.button("获取K线数据", key="get_kline"):
        if _validate_symbol(symbol):
            provider = next((p for p in cex_providers if p.name == name), None)
            if provider:
                with st.spinner(f"正在从 {provider.name} 获取 {symbol} 的 {timeframe} 数据..."):
                    data = safe_run_async(provider.get_historical_data(symbol, timeframe, limit))
                    if data:
                        df = pd.DataFrame(data)
                        fig = _create_candlestick_chart(df, symbol)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        display_error(f"无法获取 {symbol} 的K线数据。")

def main():
    """Main function to run the Streamlit application."""
    config = get_config()
    init_session_state(config)

    sidebar_controls()

    providers = get_providers(config, st.session_state)
    if not providers:
        st.error("没有可用的数据提供商。请在侧边栏中选择交易所或检查配置。")
        return

    engine = ArbitrageEngine(providers, config.get('arbitrage', {}))

    show_dashboard(engine, providers)

    if st.session_state.get('auto_refresh_enabled', False):
        interval = st.session_state.get('auto_refresh_interval', 10)
        time.sleep(interval)
        st.rerun()

if __name__ == "__main__":
    main()
