import streamlit as st
import pandas as pd
import pandas_ta as ta
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import asyncio
from datetime import datetime, timedelta

from ..providers.cex import CEXProvider
from .components import display_error

def safe_run_async(coro):
    """安全地运行异步协程，避免事件循环冲突"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在已运行的事件循环中，使用nest_asyncio
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.run(coro)
        else:
            return asyncio.run(coro)
    except RuntimeError:
        # 如果出现事件循环错误，尝试创建新的事件循环
        try:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            result = new_loop.run_until_complete(coro)
            new_loop.close()
            return result
        except Exception as e:
            st.error(f"异步操作失败: {e}")
            return None

# --- 标签 1: 实时行情数据 ---

def show_realtime_tab(providers, db_manager):
    """显示实时行情数据并将其保存到数据库。"""
    st.header("📊 实时行情数据")

    symbols_to_fetch = st.session_state.get('selected_symbols', [])
    if not symbols_to_fetch:
        st.warning("请在侧边栏中至少选择一个交易对。")
        return

    all_tickers = []

    # 使用占位符显示加载状态
    placeholder = st.empty()
    placeholder.info("正在从所有提供商获取实时数据...")

    async def fetch_all_tickers():
        tasks = []
        for provider in providers:
            # 确定提供商应获取哪些交易对
            # 这是一个简单的检查；更强大的应用可能会将提供商映射到交易对
            if isinstance(provider, CEXProvider):
                tasks.extend([provider.get_ticker(s) for s in symbols_to_fetch])
            elif provider.name == "Uniswap V3":
                tasks.extend([provider.get_ticker(s) for s in symbols_to_fetch if s in ['WETH/USDC', 'WBTC/WETH']])
            elif provider.name == "Thorchain":
                tasks.append(provider.get_ticker(st.session_state.bridge_symbol))

        return await asyncio.gather(*tasks, return_exceptions=True)

    results = safe_run_async(fetch_all_tickers())
    if results is None:
        results = []

    for res in results:
        if isinstance(res, dict) and 'error' not in res:
            res['provider_name'] = res.get('provider', 'N/A')
            all_tickers.append(res)

    if not all_tickers:
        placeholder.error("无法获取任何行情数据，请检查提供商连接。")
        return

    df = pd.DataFrame(all_tickers)
    df = df[['provider_name', 'symbol', 'last', 'bid', 'ask', 'timestamp']]
    df = df.rename(columns={'provider_name': '提供商', 'symbol': '交易对', 'last': '价格', 'bid': '买一价', 'ask': '卖一价'})
    df['价格'] = df['价格'].map('{:,.4f}'.format)

    placeholder.dataframe(df, use_container_width=True, hide_index=True)

    # 如果启用，则将数据保存到数据库
    if db_manager and st.toggle("保存数据到数据库", value=True):
        # 为数据库模式重新获取完整数据
        db_records = [t for t in all_tickers if 'error' not in t]
        if db_records:
            result = safe_run_async(db_manager.save_ticker_data(db_records))
            if result is not None:
                st.success(f"已成功保存 {len(db_records)} 条记录到数据库。")

# --- 标签 2: 市场深度 ---

def _create_depth_chart(order_book: dict) -> go.Figure:
    bids = pd.DataFrame(order_book.get('bids', []), columns=['price', 'volume']).astype(float)
    asks = pd.DataFrame(order_book.get('asks', []), columns=['price', 'volume']).astype(float)
    bids = bids.sort_values('price', ascending=False)
    asks = asks.sort_values('price', ascending=True)
    bids['cumulative'] = bids['volume'].cumsum()
    asks['cumulative'] = asks['volume'].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bids['price'], y=bids['cumulative'], name='买单', fill='tozeroy', line_color='green'))
    fig.add_trace(go.Scatter(x=asks['price'], y=asks['cumulative'], name='卖单', fill='tozeroy', line_color='red'))
    fig.update_layout(title_text=f"{order_book.get('symbol', '')} 的市场深度", xaxis_title="价格", yaxis_title="累计数量")
    return fig

def show_depth_tab(cex_providers):
    st.header("🌊 市场深度分析")
    if not cex_providers:
        st.warning("请在侧边栏中至少选择一个中心化交易所。")
        return

    col1, col2 = st.columns(2)
    selected_exchange_name = col1.selectbox("选择交易所", options=[p.name for p in cex_providers])
    symbol = col2.text_input("输入交易对", "BTC/USDT", key="depth_symbol")

    if st.button("获取市场深度"):
        provider = next((p for p in cex_providers if p.name == selected_exchange_name), None)
        if not provider:
            st.error("未找到选定的提供商。")
            return

        with st.spinner(f"正在从 {provider.name} 获取 {symbol} 的订单簿..."):
            order_book = safe_run_async(provider.get_order_book(symbol, limit=50))
            if order_book is None:
                order_book = {'bids': [], 'asks': []}
            
            if order_book and 'error' in order_book:
                display_error(f"无法获取订单簿: {order_book['error']}")
            else:
                st.plotly_chart(_create_depth_chart(order_book), use_container_width=True)

# --- 标签 3: 套利机会 ---

def show_arbitrage_tab(arbitrage_engine):
    st.header("⚡ 套利机会")
    st.info("此标签页分析所有选定提供商之间的价格差异，以发现计入预估费用后仍然有利可图的套利机会。")

    if st.button("寻找套利机会"):
        with st.spinner("正在分析所有交易对和品种..."):
            try:
                # 用UI的最新阈值更新引擎
                arbitrage_engine.profit_threshold = st.session_state.get('arbitrage_threshold', 0.2)

                opportunities = safe_run_async(arbitrage_engine.find_opportunities(st.session_state.selected_symbols))
                if opportunities is None:
                    opportunities = []

                if not opportunities:
                    st.success("✅ 根据当前设置，未发现有利可图的套利机会。")
                else:
                    st.success(f"🎉 发现 {len(opportunities)} 个套利机会！")

                    # 创建一个DataFrame以便清晰、可排序和信息丰富的表格显示
                    df = pd.DataFrame(opportunities)

                    # 格式化并选择主表的列
                    display_df = df[[
                        'symbol', 'buy_at', 'sell_at', 'buy_price', 'sell_price',
                        'gross_profit_usd', 'total_fees_usd', 'net_profit_usd', 'profit_percentage'
                    ]]

                    # 改进列名以便显示
                    display_df.columns = [
                        '交易对', '买入平台', '卖出平台', '买入价 ($)', '卖出价 ($)',
                        '毛利润 ($)', '预估手续费 ($)', '净利润 ($)', '净利润 %'
                    ]

                    # 数字的自定义样式
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "买入价 ($)": st.column_config.NumberColumn(format="$%.4f"),
                            "卖出价 ($)": st.column_config.NumberColumn(format="$%.4f"),
                            "毛利润 ($)": st.column_config.NumberColumn(format="$%.4f"),
                            "预估手续费 ($)": st.column_config.NumberColumn(format="$%.4f"),
                            "净利润 ($)": st.column_config.NumberColumn(format="$%.4f"),
                            "净利润 %": st.column_config.NumberColumn(format="%.4f%%"),
                        }
                    )
            except Exception as e:
                display_error(f"套利分析过程中发生错误: {e}")

# --- 标签 4: 历史分析 ---

def show_history_tab(db_manager):
    st.header("📜 历史数据分析")
    if not db_manager:
        st.warning("数据库连接不可用，此功能已禁用。")
        return

    st.info("查询并可视化存储在数据库中的历史行情数据。")

    col1, col2, col3 = st.columns(3)
    symbol = col1.text_input("交易对", "BTC/USDT", key="history_symbol_input")
    start_date = col2.date_input("开始日期", datetime.now() - timedelta(days=1))
    end_date = col3.date_input("结束日期", datetime.now())

    if st.button("查询历史数据"):
        if not symbol:
            st.warning("请输入一个交易对。")
            return

        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        with st.spinner(f"正在查询 {symbol} 从 {start_date} 到 {end_date} 的数据..."):
            try:
                df = safe_run_async(db_manager.query_historical_data(symbol, start_datetime, end_datetime))
                if df is None:
                    st.error("无法获取历史数据")
                    return
                if df.empty:
                    st.success("未找到符合所选条件的任何历史数据。")
                else:
                    st.dataframe(df, use_container_width=True)
                    # 创建一个简单的价格图表
                    fig = go.Figure()
                    for provider in df['provider_name'].unique():
                        provider_df = df[df['provider_name'] == provider]
                        fig.add_trace(go.Scatter(x=provider_df['timestamp'], y=provider_df['price'], mode='lines', name=provider))
                    fig.update_layout(title=f"{symbol} 的价格历史", xaxis_title="时间戳", yaxis_title="价格 (USD)")
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                display_error(f"查询数据库时发生错误: {e}")

# --- 标签 5: 转账费用对比 ---

def show_fees_tab(cex_providers):
    """显示一个用于比较各交易所存提费用的标签页。"""
    st.header("💸 转账费用对比")
    st.info("在所有选定的中心化交易所中，比较特定资产的充值和提现费用及可用网络。")

    if not cex_providers:
        st.warning("请在侧边栏中至少选择一个中心化交易所。")
        return

    asset = st.text_input("输入要比较的资产代码", "USDT", key="fee_asset_input").upper()

    if st.button("比较转账费用"):
        if not asset:
            st.warning("请输入一个资产代码。")
            return

        async def fetch_all_fees():
            # 使用新的 get_transfer_fees 方法
            tasks = [provider.get_transfer_fees(asset) for provider in cex_providers]
            return await asyncio.gather(*tasks, return_exceptions=True)

        with st.spinner(f"正在从所有选定的交易所获取 {asset} 的转账费用..."):
            results = safe_run_async(fetch_all_fees())
            if results is None:
                results = []

        processed_data = []
        failed_providers = []
        for i, res in enumerate(results):
            provider_name = cex_providers[i].name
            if isinstance(res, dict) and 'error' not in res:
                # 处理充值
                for network, details in res.get('deposit', {}).items():
                    processed_data.append({
                        '交易所': provider_name.capitalize(),
                        '类型': '充值',
                        '资产': asset,
                        '网络': network,
                        '手续费': details.get('fee', 0.0),
                        '是否为百分比': details.get('percentage', False)
                    })
                # 处理提现
                for network, details in res.get('withdraw', {}).items():
                    processed_data.append({
                        '交易所': provider_name.capitalize(),
                        '类型': '提现',
                        '资产': asset,
                        '网络': network,
                        '手续费': details.get('fee'),
                        '是否为百分比': details.get('percentage', False)
                    })
            else:
                # 收集失败的提供商名称
                failed_providers.append(provider_name.capitalize())

        # 为所有失败的提供商显示一条错误消息
        if failed_providers:
            st.error(f"无法获取以下交易所的费用数据: {', '.join(failed_providers)}。它们可能不支持资产 '{asset}' 或 API 不可用。")

        if not processed_data:
            st.warning("未能成功获取任何交易所的费用数据。")
        else:
            df = pd.DataFrame(processed_data)
            df = df[['交易所', '类型', '网络', '手续费', '是否为百分比', '资产']]
            st.dataframe(df, use_container_width=True, hide_index=True)

# --- 标签 6: 定性交易所对比 ---

def show_comparison_tab(qualitative_data: dict):
    """显示一个用于比较交易所定性数据的标签页。"""
    st.header("🏢 交易所对比")
    st.info("查看手动整理的关于不同交易所的信息。")

    if not qualitative_data:
        st.warning("未找到定性数据。请检查 `qualitative_data.yml` 文件。")
        return

    # 为YAML中的键创建中文映射
    key_to_chinese = {
        'security_measures': '安全措施',
        'customer_service': '客户服务',
        'platform_stability': '平台稳定性',
        'fund_insurance': '资金保险',
        'regional_restrictions': '地区限制',
        'withdrawal_limits': '提现限额',
        'withdrawal_speed': '提现速度',
        'supported_cross_chain_bridges': '支持的跨链桥',
        'api_support_details': 'API支持详情',
        'fee_discounts': '手续费折扣',
        'margin_leverage_details': '杠杆交易详情',
        'maintenance_schedule': '维护计划',
        'user_rating_summary': '用户评分摘要',
        'tax_compliance_info': '税务合规信息'
    }

    exchange_list = list(qualitative_data.keys())
    selected_exchange = st.selectbox(
        "选择一个交易所查看详情",
        options=exchange_list,
        format_func=lambda x: x.capitalize()
    )

    if selected_exchange:
        data = qualitative_data[selected_exchange]
        st.subheader(f"{selected_exchange.capitalize()} 的详情")

        # 使用 key_to_chinese 的键顺序以保持一致的布局
        key_order = list(key_to_chinese.keys())

        # 创建一个两列布局以提高可读性
        col1, col2 = st.columns(2)

        # 将项目分配到两列中
        for i, key in enumerate(key_order):
            if key in data:
                display_key = key_to_chinese.get(key, key.replace('_', ' ').capitalize())
                value = data[key]

                # 在列之间交替
                if i % 2 == 0:
                    with col1:
                        st.markdown(f"**{display_key}**")
                        st.markdown(f"<div style='background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 10px;'>{value}</div>", unsafe_allow_html=True)
                else:
                    with col2:
                        st.markdown(f"**{display_key}**")
                        st.markdown(f"<div style='background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 10px;'>{value}</div>", unsafe_allow_html=True)

# --- 标签 7: K线图与历史数据 ---

def _create_candlestick_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
    """
    Creates a Plotly candlestick chart from a DataFrame.
    If the DataFrame contains an RSI column, it adds a subplot for the RSI.
    """
    rsi_col = next((col for col in df.columns if 'RSI' in col), None)

    if rsi_col:
        # Create a figure with 2 rows; top for candlestick, bottom for RSI
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                           vertical_spacing=0.05, row_heights=[0.7, 0.3])
    else:
        # Create a regular figure with a single row
        fig = make_subplots(rows=1, cols=1)

    # --- Candlestick Trace ---
    fig.add_trace(go.Candlestick(
        x=pd.to_datetime(df['timestamp'], unit='ms'),
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name=symbol
    ), row=1, col=1)

    # --- RSI Trace (if exists) ---
    if rsi_col:
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(df['timestamp'], unit='ms'),
            y=df[rsi_col],
            name='RSI',
            line=dict(color='orange', width=1)
        ), row=2, col=1)
        # Add overbought/oversold lines for RSI
        fig.add_hline(y=70, line_dash="dash", line_color="red", line_width=1, row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", line_width=1, row=2, col=1)
        fig.update_yaxes(title_text="RSI", row=2, col=1)

    # --- Layout ---
    fig.update_layout(
        title_text=f"{symbol} 价格走势",
        xaxis_rangeslider_visible=False,
        yaxis_title="价格 (USD)"
    )
    # Remove the shared x-axis title for the top plot
    fig.update_xaxes(showticklabels=True, row=1, col=1)
    fig.update_xaxes(title_text="日期", row=2 if rsi_col else 1, col=1)

    return fig

def show_kline_tab(cex_providers):
    """显示一个用于获取和可视化历史K线数据的标签页。"""
    st.header("📈 K线图与历史数据")
    st.info("从此处的交易所获取历史K线（OHLCV）数据。数据在首次获取时会被缓存到本地 CSV 文件中，以加快后续加载速度。")

    if not cex_providers:
        st.warning("请在侧边栏中至少选择一个中心化交易所。")
        return

    # --- UI Controls ---
    col1, col2, col3, col4 = st.columns(4)
    selected_exchange_name = col1.selectbox("选择交易所", options=[p.name for p in cex_providers], key="kline_exchange")
    symbol = col2.text_input("输入交易对", "BTC/USDT", key="kline_symbol")
    timeframe = col3.selectbox("选择时间周期", options=['1d', '4h', '1h', '30m', '5m'], key="kline_timeframe")
    limit = col4.number_input("数据点数量", min_value=20, max_value=500, value=100, key="kline_limit")

    show_rsi = st.checkbox("显示RSI (14周期)", key="show_rsi")

    if st.button("获取并显示K线数据", key="get_kline_data"):
        provider = next((p for p in cex_providers if p.name == selected_exchange_name), None)
        if not provider:
            display_error("未找到选定的提供商。")
            return

        with st.spinner(f"正在从 {provider.name} 获取 {symbol} 的 {timeframe} 数据..."):
            data = safe_run_async(provider.get_historical_data(symbol, timeframe, limit))

            if not data:
                display_error(f"无法获取数据。提供商可能不支持此交易对/时间周期，或者API可能不可用。")
                return

            df = pd.DataFrame(data)

            # --- Technical Analysis Calculation ---
            if show_rsi:
                if 'close' in df.columns:
                    # Use pandas-ta to calculate RSI and append it to the DataFrame
                    df.ta.rsi(length=14, append=True)
                else:
                    st.warning("无法计算RSI，因为数据中缺少 'close' 列。")

            st.success(f"成功获取 {len(df)} 条记录。")

            # Display chart
            st.plotly_chart(_create_candlestick_chart(df, symbol), use_container_width=True)

            # Display data table in an expander
            with st.expander("查看原始数据 (包含技术指标)"):
                st.dataframe(df, use_container_width=True)
