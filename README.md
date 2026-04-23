# A股量化选股系统 — 交付文档

## 一、项目概述

基于"二次突破"量化策略的A股选股系统，自动扫描全市场，识别涨停起爆→缩量整理→二次突破的买入信号，并跟踪止损。


- **技术栈**: Python/FastAPI + React/Vite + ECharts + Tushare

---

## 二、策略说明

### 二次突破策略

```
起爆日 → 缩量整理 → 二次突破买入 → SMA5止损
```

| 阶段 | 条件 |
|------|------|
| 起爆 | 当日涨幅 ≥ 9.5%，成交量 ≥ 20日均量 × 2.0 |
| 整理 | 3~15日内股价不破支撑位，成交量缩至起爆日 × 0.5 以下 |
| 买入 | 收盘价站上突破位且放量确认 |
| 止损 | 收盘价跌破 SMA5 |

### 可调参数

| 参数 | 默认值 | 含义 |
|------|--------|------|
| 涨幅阈值 | 9.5% | 起爆日最低涨幅 |
| 量比阈值 | 2.0 | 起爆日量比倍数 |
| 缩量比 | 0.5 | 整理期量能上限（相对起爆日） |
| 量均线窗口 | 20 | 计算均量的回溯天数 |
| 整理最少天数 | 3 | 整理期最短 |
| 整理最多天数 | 15 | 整理期最长 |

---

## 三、功能清单

### 3.1 全市场扫描

- 一键扫描全部A股（过滤ST/退市/北交所/科创板）
- SSE 实时进度推送
- 结果按买入日排序，支持列排序

### 3.2 策略参数可调

- 前端面板调节6个策略参数
- 参数自动保存到浏览器 localStorage
- 扫描和个股信号均使用当前参数

### 3.3 K线图详情

- 红涨绿跌K线 + MA5/MA20均线
- 起爆点/买入点标注
- 突破位/支撑位虚线
- 整理区间阴影
- 成交量柱状图
- 拖拽缩放 + 滑块

### 3.4 定时自动扫描

- 每日指定时间自动运行全市场扫描
- 前端可开关、调整时间
- 自动扫描结果覆盖上次数据

### 3.5 止损监控推送

- 从扫描结果添加股票到监控列表
- 刷新数据自动检测止损信号变化
- 新触发止损时浏览器推送通知
- 扫描完成后自动刷新监控数据

### 3.6 多股对比

- 勾选多只股票，点击"对比"
- 多个K线图并排展示
- 紧凑模式适配小图

### 3.7 股票搜索

- 输入代码或名称实时搜索
- 点击跳转K线详情

---

## 四、页面说明

### 扫描页（首页）

1. 点击"开始扫描"启动全市场扫描
2. 进度条实时显示扫描进度
3. 展开"策略参数"调节策略阈值
4. 展开"定时扫描"设置自动扫描时间
5. 结果表格：点击行进入K线详情，点"监控"加入监控列表，勾选后点"对比"进入多股对比

### 监控页

1. 展示所有监控中的股票
2. 点击"刷新数据"更新最新价和止损状态
3. 新触发止损时弹出浏览器通知
4. 点"移除"退出监控

### K线详情页

1. 信号卡片展示关键数据（起爆日/买入价/浮盈等）
2. K线图展示完整走势和策略标注
3. 点击"← 返回列表"回到首页

### 多股对比页

1. 多个K线图并排展示
2. 每个图独立支持缩放
3. 紧凑布局适配2~6只股票

---

## 五、API 接口

### 扫描相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/scan/results` | 获取扫描结果 |
| POST | `/api/scan/start` | 启动扫描（body: `{strategy: {...}, days: 120, delay: 0.3}`） |
| GET | `/api/scan/status` | SSE 扫描进度流 |
| GET | `/api/scan/state` | 当前扫描状态 |
| GET | `/api/scan/params` | 当前策略参数 |

### 定时扫描

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/scan/schedule` | 获取定时配置 |
| PUT | `/api/scan/schedule` | 更新定时配置（body: `{enabled, hour, minute}`） |

### 个股

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stock/{code}/history?days=120` | K线数据 |
| GET | `/api/stock/{code}/signals?days=120&rise_threshold=9.5` | 信号数据（可传策略参数） |
| GET | `/api/stock/search?q=平安` | 搜索股票 |

### 监控

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/watchlist` | 监控列表 |
| POST | `/api/watchlist` | 添加监控（body: `{code, name, entry_price, entry_date}`） |
| DELETE | `/api/watchlist/{code}` | 移除监控 |
| POST | `/api/watchlist/refresh` | 刷新数据，返回新触发止损 |
| GET | `/api/watchlist/alerts` | 已触发止损列表 |

---

## 六、部署说明

### 环境变量（必填）

| 变量 | 说明 | 示例 |
|------|------|------|
| `TUSHARE_TOKEN` | Tushare API Token | `你的token` |
| `TUSHARE_API_URL` | Tushare 镜像地址 | `http://tushare.xyz` |

### 环境变量（可选）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SCHEDULE_ENABLED` | 定时扫描开关 | `false` |
| `SCHEDULE_HOUR` | 扫描时间-时 | `15` |
| `SCHEDULE_MINUTE` | 扫描时间-分 | `30` |
| `PORT` | 服务端口 | `8000` |

### 本地开发

```bash
# 后端
cd a_stock_screener
pip install -r requirements.txt
python -m uvicorn server.app:app --port 8000

# 前端
cd web && npm install && npm run dev

# 访问 http://localhost:5173
```

### 单服务模式

```bash
cd a_stock_screener
cd web && npm install && npm run build && cd ..
python start.py
# 访问 http://localhost:8000
```

### Docker 部署

```bash
docker build -t a-stock-screener .
docker run -d -p 8000:8000 \
  -e TUSHARE_TOKEN=你的token \
  -e TUSHARE_API_URL=http://tushare.xyz \
  a-stock-screener
```

### Railway 部署

1. GitHub 创建仓库，推送代码
2. Railway → New Project → Deploy from GitHub repo
3. Settings → Generate Domain 生成公网地址
4. Variables 添加 `TUSHARE_TOKEN` 和 `TUSHARE_API_URL`
5. 重新部署生效

---

## 七、项目结构

```
a_stock_screener/
├── server/                  # FastAPI 后端
│   ├── app.py              # 应用入口 + SPA静态服务
│   ├── scan_runner.py      # 扫描引擎（线程+SSE广播）
│   ├── scheduler.py        # APScheduler 定时任务
│   ├── watchlist.py        # 监控列表管理
│   ├── models.py           # Pydantic 数据模型
│   └── api/
│       ├── scan.py         # 扫描相关API
│       ├── stock.py        # 个股API
│       ├── schedule.py     # 定时扫描API
│       └── watchlist.py    # 监控API
├── strategy.py             # 二次突破策略逻辑
├── data_fetcher.py         # Tushare 数据获取
├── start.py                # 单服务启动入口
├── Dockerfile              # Docker 构建
├── railway.toml            # Railway 配置
├── requirements.txt        # Python 依赖
└── web/                    # React 前端
    ├── src/
    │   ├── App.jsx
    │   ├── api/client.js
    │   ├── components/
    │   │   ├── Dashboard.jsx
    │   │   ├── ScanControls.jsx
    │   │   ├── StrategyParams.jsx
    │   │   ├── ScheduleSettings.jsx
    │   │   ├── ResultsTable.jsx
    │   │   ├── StockDetail.jsx
    │   │   ├── KlineChart.jsx
    │   │   ├── SignalCard.jsx
    │   │   ├── SearchInput.jsx
    │   │   ├── Watchlist.jsx
    │   │   ├── CompareView.jsx
    │   │   └── Layout.jsx
    │   ├── styles.css
    │   └── main.jsx
    ├── vite.config.js
    └── package.json
```

---

## 八、注意事项

1. **数据时效**: 扫描结果是快照，非实时行情。定时扫描可保证每日收盘后数据更新
2. **Tushare 限流**: 全市场扫描约5000+只股票，每只间隔0.3秒，全程约25分钟
3. **浏览器通知**: 首次使用监控功能需授权浏览器通知权限
4. **代理冲突**: 本地开发时，如使用Clash等代理，需确保localhost不走代理
5. **免责声明**: 本系统仅供学习研究，不构成投资建议。股市有风险，投资需谨慎
