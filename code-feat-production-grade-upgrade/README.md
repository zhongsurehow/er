# 生产级数字货币交易所对比分析工具

这是一个高性能、可扩展、功能丰富的生产级数字货币分析工具。它集成了多个数据源（中心化交易所、去中心化交易所、跨链桥），提供全面的交易所对比功能，包括实时行情、K线图、市场深度、套利机会发现、费用分析和定性评估。

## 核心功能

- **多维度交易所对比**:
  - **实时行情**: 通过 WebSocket 实时获取多个交易所的行情数据。
  - **历史K线图 (带缓存)**: 获取并展示历史K线图。首次获取的数据会 **自动缓存** 到本地 `data/` 目录下的 CSV 文件中，加速后续加载。
  - **市场深度**: 动态、交互式地展示所选交易对的市场深度图。
  - **跨平台套利**: 内置套利引擎，实时分析价差，并精确计算扣除手续费后的净利润。
  - **费用分析**: 对比不同交易所、不同资产的 **充值 (Deposit)** 和 **提现 (Withdrawal)** 网络及手续费。
  - **定性数据对比**: 提供一个全面的、手动维护的交易所信息库 (`config/qualitative_data.yml`)，包含安全、客服、费率等多维度信息。
- **数据持久化**:
  - **历史K线缓存**: 将下载的K线数据保存为CSV文件，避免重复请求。
  - **实时数据存储**: (可选) 使用 `asyncpg` 与 `PostgreSQL/TimescaleDB` 高效集成，存储实时行情数据以供历史分析。
- **现代化Web界面**:
  - 基于 `Streamlit` 构建，通过清晰的标签页展示不同功能模块。
- **容器化部署**:
  - 提供 `Dockerfile` 和 `docker-compose.yml`，一键启动整个应用。

## 技术架构与原理

项目采用模块化的 `src` 布局，将业务逻辑、UI和数据提供者清晰分离，易于维护和扩展。

### 新版文件结构

```
.
├── src/                    # 应用源代码
│   ├── app.py              # Streamlit 应用主入口
│   ├── config.py           # 配置加载模块
│   ├── config_loader.py    # UI无关的配置加载逻辑
│   ├── db.py               # 数据库管理器
│   ├── engine.py           # 套利引擎
│   ├── providers/          # 数据提供者模块 (CEX, DEX, Bridge)
│   └── ui/                 # UI 组件和标签页模块
├── config/                 # 配置文件
│   ├── fees.yml            # 套利引擎的手续费配置
│   └── qualitative_data.yml # 交易所定性信息
├── data/                   # 本地数据缓存目录 (自动创建)
├── tests/                  # 测试套件
├── .env.example            # 环境变量模板
├── requirements.txt        # Python 依赖
├── Dockerfile
└── docker-compose.yml
```

---

## 运行指南

您可以选择通过本地 Python 环境或 Docker 来运行此应用。

### 方案一：在本地 Python 环境中运行 (推荐用于开发)

1.  **克隆项目**
    ```bash
    git clone <your-repo-url>
    cd <project-directory>
    ```

2.  **设置 Python 环境**
    -   建议使用 Python 3.9+。
    -   创建并激活一个虚拟环境：
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        # On Windows, use: venv\Scripts\activate
        ```

3.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```

4.  **创建并配置环境变量文件 (`.env`)**
    -   将 `.env.example` 文件复制一份，并重命名为 `.env`。
        ```bash
        cp .env.example .env
        ```
    -   打开 `.env` 文件并根据需要进行配置。对于大部分公开数据的功能，您**无需**填写API密钥。
        -   `DB_DSN`: (可选) 用于存储实时数据的数据库连接字符串。如果留空，相关功能将被禁用。
        -   `RPC_URL_ETHEREUM`: (可选) 您的以太坊主网 RPC URL，用于DEX数据。
        -   `BINANCE_API_KEY`, `OKX_API_KEY` 等: (可选) 目前主要用于获取转账费用，未来可用于私有API功能。

5.  **启动应用**
    -   在项目根目录下运行以下命令：
        ```bash
        streamlit run src/app.py
        ```
    -   应用将在您的浏览器中打开。

### 方案二：通过 Docker 运行

1.  **准备环境**: 确保已安装 [Docker](https://www.docker.com/products/docker-desktop/) 和 [Docker Compose](https://docs.docker.com/compose/install/)。

2.  **配置 `.env` 文件**: 同上，复制 `.env.example` 到 `.env` 并进行配置。

3.  **启动服务**:
    ```bash
    docker-compose up --build
    ```

4.  **访问应用**: 打开浏览器，访问 `http://localhost:8501`。

---

## 如何运行测试

测试套件用于验证核心业务逻辑（如套利引擎）的正确性。

1.  **安装测试依赖**
    ```bash
    pip install pytest pytest-asyncio
    ```
2.  **运行测试**
    -   在项目根目录下，直接运行 `pytest` 即可。
    ```bash
    pytest
    ```
