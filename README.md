# 🤖 Trading Machine

一个专业的加密货币交易机器人，支持多交易所、策略回测、Telegram交互等功能。

## ✨ 功能特性

- 🏢 **多交易所支持**: Binance、OKX、Bybit
- 📊 **策略系统**: 移动平均交叉、RSI策略等
- 🔄 **回测功能**: 历史数据策略验证
- 📱 **Telegram集成**: 实时通知和交互操作
- ⚡ **异步架构**: 高性能并发处理
- 🛡️ **风险管理**: 止损止盈、仓位管理
- 📈 **数据获取**: 实时和历史K线数据

## 📁 项目结构

```
trading-machine/
├── trading_bot/
│   ├── config/          # 配置管理
│   ├── exchanges/       # 交易所接口
│   ├── strategies/      # 交易策略
│   ├── backtesting/     # 回测引擎
│   ├── telegram_bot/    # Telegram机器人
│   ├── core/           # 核心交易引擎
│   └── utils/          # 工具函数
├── main.py             # 主程序入口
├── requirements.txt    # 依赖包
└── .env.example       # 环境变量模板
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入你的API密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入交易所和Telegram的配置信息。

### 3. 运行实盘交易

```bash
python main.py live
```

### 4. 运行策略回测

```bash
# 回测移动平均策略
python main.py backtest --strategy ma_crossover --symbol BTC/USDT --days 30

# 回测RSI策略
python main.py backtest --strategy rsi --symbol ETH/USDT --days 60
```

## 📊 策略说明

### 移动平均交叉策略 (MA Crossover)
- 快速MA上穿慢速MA时买入
- 快速MA下穿慢速MA时卖出
- 结合RSI指标过滤信号

### RSI策略
- RSI超卖反弹时买入
- RSI超买回落时卖出
- 支持背离信号识别

## 🔧 交易所配置

### Binance
1. 登录Binance账户
2. 创建API密钥（建议使用测试网）
3. 配置权限：现货交易、期货交易、读取信息

### OKX
1. 登录OKX账户
2. 创建API密钥
3. 设置交易权限和IP白名单

### Bybit
1. 登录Bybit账户  
2. 创建API密钥
3. 配置相应权限

## 📱 Telegram机器人设置

### 1. 创建机器人
1. 在Telegram中搜索 @BotFather
2. 发送 `/newbot` 创建新机器人
3. 获取Bot Token

### 2. 获取Chat ID
1. 将机器人添加到群组或私聊
2. 发送消息给机器人
3. 访问 `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` 获取Chat ID

### 3. 可用命令
- `/balance [exchange]` - 查看余额
- `/positions [exchange]` - 查看持仓
- `/orders [exchange]` - 查看订单
- `/buy <exchange> <symbol> <amount> [price]` - 买入
- `/sell <exchange> <symbol> <amount> [price]` - 卖出
- `/cancel <exchange> <order_id> <symbol>` - 取消订单
- `/price <exchange> <symbol>` - 查看价格
- `/leverage <exchange> <symbol> <leverage>` - 设置杠杆

## ⚠️ 风险提示

1. **使用测试网**: 强烈建议先在测试网环境下运行
2. **小额测试**: 实盘前请用小额资金测试
3. **风险管理**: 设置合理的止损和仓位大小
4. **监控运行**: 定期检查机器人运行状态
5. **策略验证**: 充分回测验证策略有效性

## 🛠️ 开发说明

### 添加新策略
1. 继承 `BaseStrategy` 类
2. 实现 `analyze()` 方法
3. 在 `strategies/__init__.py` 中注册

### 添加新交易所
1. 继承 `BaseExchange` 类
2. 实现所有抽象方法
3. 在 `exchanges/__init__.py` 中注册

### 自定义指标
在策略中使用 `talib` 库计算技术指标。

## 📈 回测结果示例

```
📊 BACKTEST RESULTS
==================================================
Strategy: ma_crossover
Symbol: BTC/USDT
Period: 2024-05-25 to 2024-06-25 (30 days)

Performance:
  Initial Balance: $10,000.00
  Final Balance: $10,456.78
  Total Return: $456.78 (4.57%)
  Max Drawdown: $234.56 (2.35%)
  Sharpe Ratio: 1.23

Trade Statistics:
  Total Trades: 15
  Winning Trades: 9
  Losing Trades: 6
  Win Rate: 60.0%
  Average Win: $123.45
  Average Loss: $67.89
  Profit Factor: 1.82
```

## 📄 许可证

本项目仅供学习和研究使用，使用者需自行承担交易风险。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进项目。

## 📞 支持

如有问题，请创建Issue或联系开发者。