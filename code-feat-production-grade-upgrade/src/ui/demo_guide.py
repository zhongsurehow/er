import streamlit as st

def show_demo_guide():
    """显示演示模式功能指南"""
    st.markdown("## 🎯 功能演示指南")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 实时行情监控")
        st.info(
            "• 多交易所价格对比\n"
            "• 实时价格更新\n"
            "• 价差分析\n"
            "• 交易量监控"
        )
        
        st.markdown("### 📈 市场深度分析")
        st.info(
            "• 买卖盘深度图表\n"
            "• 流动性分析\n"
            "• 价格影响评估\n"
            "• 订单簿可视化"
        )
        
        st.markdown("### ⚡ 套利机会识别")
        st.info(
            "• 跨交易所套利\n"
            "• 实时利润计算\n"
            "• 风险评估\n"
            "• 执行建议"
        )
    
    with col2:
        st.markdown("### 💰 费用对比分析")
        st.info(
            "• 交易手续费对比\n"
            "• 提现费用分析\n"
            "• VIP等级优惠\n"
            "• 成本效益评估"
        )
        
        st.markdown("### 🏢 交易所对比")
        st.info(
            "• 安全性评级\n"
            "• 用户体验评分\n"
            "• 支持币种数量\n"
            "• 监管合规状态"
        )
        
        st.markdown("### 📚 历史数据分析")
        st.info(
            "• 价格历史趋势\n"
            "• 套利机会回测\n"
            "• 市场波动分析\n"
            "• 数据导出功能"
        )
    
    st.markdown("---")
    
    st.markdown("### 🚀 开始使用")
    
    tab1, tab2, tab3 = st.tabs(["快速开始", "API配置", "常见问题"])
    
    with tab1:
        st.markdown(
            """**立即体验演示功能：**
            
            1. 📊 点击 **实时行情** 标签页查看模拟价格数据
            2. 📈 浏览 **市场深度** 了解订单簿分析
            3. ⚡ 探索 **套利机会** 发现潜在利润
            4. 💰 查看 **费用对比** 了解成本分析
            5. 🏢 访问 **交易所对比** 查看定性评估
            
            💡 **提示：** 所有功能都可以在演示模式下正常使用！"""
        )
    
    with tab2:
        st.markdown(
            """**配置真实数据源：**
            
            1. 🔑 在左侧边栏选择要使用的交易所
            2. 📝 展开对应交易所的API密钥配置
            3. 🔐 输入您的API Key和Secret
            4. ✅ 系统将自动切换到真实数据模式
            
            ⚠️ **安全提醒：** API密钥仅存储在浏览器会话中，不会被永久保存。"""
        )
    
    with tab3:
        st.markdown(
            """**常见问题解答：**
            
            **Q: 演示模式的数据是真实的吗？**
            A: 演示模式使用模拟数据，用于功能展示。配置API密钥后可获取真实市场数据。
            
            **Q: 需要配置所有交易所的API吗？**
            A: 不需要。您可以只配置感兴趣的交易所，系统会自动适配。
            
            **Q: API密钥安全吗？**
            A: API密钥仅存储在浏览器会话中，页面刷新后需要重新输入。建议使用只读权限的API密钥。
            
            **Q: 如何获取API密钥？**
            A: 请访问对应交易所官网，在API管理页面创建新的API密钥。"""
        )

def show_feature_highlights():
    """显示功能亮点"""
    st.markdown("### ✨ 核心功能亮点")
    
    features = [
        {
            "icon": "🚀",
            "title": "生产级架构",
            "description": "异步处理、连接池、错误恢复机制"
        },
        {
            "icon": "📊",
            "title": "实时数据",
            "description": "毫秒级价格更新，多交易所同步"
        },
        {
            "icon": "🔍",
            "title": "智能分析",
            "description": "自动套利识别，风险评估算法"
        },
        {
            "icon": "💾",
            "title": "数据存储",
            "description": "TimescaleDB时序数据库，历史分析"
        },
        {
            "icon": "🛡️",
            "title": "安全可靠",
            "description": "API密钥本地存储，只读权限推荐"
        },
        {
            "icon": "🎨",
            "title": "现代界面",
            "description": "响应式设计，直观的数据可视化"
        }
    ]
    
    cols = st.columns(3)
    for i, feature in enumerate(features):
        with cols[i % 3]:
            st.markdown(
                f"""<div style="
                    border: 1px solid #e0e0e0;
                    border-radius: 10px;
                    padding: 20px;
                    margin: 10px 0;
                    text-align: center;
                    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                ">
                    <h2 style="margin: 0; color: #333;">{feature['icon']}</h2>
                    <h4 style="margin: 10px 0; color: #555;">{feature['title']}</h4>
                    <p style="margin: 0; color: #666; font-size: 14px;">{feature['description']}</p>
                </div>""",
                unsafe_allow_html=True
            )