# 基金净值估算 MVP

一个基于 FastAPI + React 的基金净值估算 MVP，支持基金持仓管理、组合估值、基金净值趋势查看，以及本地 SQLite 数据持久化。

## 项目能力

- 持仓更新（买入金额 / 卖出金额）、删除
- 单基金估值
- 组合总览估值
- 净值未更新时记录待处理金额（待确认金额 / 待卖出金额），净值更新后自动确认份额
- 估值失败项保留错误信息，不阻断其他基金计算
- 基金历史净值趋势查看
- 本地 SQLite 持久化存储

## 技术栈

- 后端：FastAPI、SQLAlchemy、SQLite、天天基金（东方财富接口）、Pydantic
- 前端：React 19、Vite、TypeScript、Ant Design、ECharts、Axios

## 目录结构

```text
jijin/
├─ backend/                 # FastAPI 后端
│  ├─ app/
│  │  ├─ api/               # 路由层
│  │  ├─ core/              # 配置与异常定义
│  │  ├─ db/                # 数据库连接
│  │  ├─ models/            # ORM 模型
│  │  ├─ repositories/      # 数据访问层
│  │  ├─ schemas/           # 请求/响应模型
│  │  └─ services/          # 基金数据与估值服务
│  ├─ data/                 # SQLite 数据文件目录
│  └─ tests/                # 后端测试
├─ frontend/                # React 前端
│  └─ src/
├─ doc/                     # PRD、技术方案、开发总结
└─ README.md
```

## 环境要求

- Python 3.11 或更高版本
- Node.js 18 或更高版本
- npm 9 或更高版本

## 快速启动

### 1. 启动后端

在项目根目录执行：

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -e .[dev]
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

后端启动后可访问：

- API 根前缀：`http://127.0.0.1:8000/api/v1`
- 健康检查：`http://127.0.0.1:8000/api/v1/health`

### 2. 启动前端

新开一个终端，在项目根目录执行：

```bash
cd frontend
npm install
npm run dev
```

前端默认启动在：`http://127.0.0.1:5173`

当前前端默认请求后端地址：`http://127.0.0.1:8000/api/v1`

## 数据存储

- 本地数据库文件：`backend/data/app.db`
- 后端启动时会自动创建表结构
- 若历史数据库缺少 `position_date` 或 `pending_amount` 字段，后端会在启动时自动补齐并回填数据

## 常用命令

### 后端测试

```bash
cd backend
pytest
```

### 前端构建

```bash
cd frontend
npm run build
```

## 核心接口

### 持仓管理

- `GET /api/v1/positions`：获取持仓列表
- `POST /api/v1/positions`：创建初始持仓（仅支持 `trade_type=buy`）
- `PUT /api/v1/positions/{id}`：更新持仓（支持买入/卖出金额）
- `DELETE /api/v1/positions/{id}`：删除持仓

#### 持仓更新规则

- 请求字段统一使用金额：`amount`
- 交易方向使用：`trade_type`，可选 `buy` / `sell`
- 买入与卖出逻辑对称：
	- 当日单位净值可用：立即按当日净值确认份额
	- 当日单位净值不可用（通常 15:00 前）：先写入待处理金额，展示为
		- 买入：`pending_amount > 0`，前端展示“待确认金额”
		- 卖出：`pending_amount < 0`，前端展示“待卖出金额”
- 后续刷新估值后，若当日单位净值已公布，会自动确认 pending 对应的份额变动

#### 请求示例

`POST /api/v1/positions`

```json
{
	"fund_code": "161725",
	"position_date": "2026-03-24",
	"amount": 10000,
	"trade_type": "buy"
}
```

`PUT /api/v1/positions/{id}`

```json
{
	"position_date": "2026-03-24",
	"amount": 2000,
	"trade_type": "sell"
}
```

### 基金信息

- `GET /api/v1/funds/{fund_code}`：获取基金基础信息和当前估值
- `GET /api/v1/funds/{fund_code}/history`：获取基金历史净值趋势

### 估值

- `POST /api/v1/valuation/fund`：计算单基金估值
- `GET /api/v1/valuation/portfolio`：计算组合估值

### OpenClaw 工具接口

- `GET /api/v1/openclaw/health`：OpenClaw 健康检查
- `POST /api/v1/openclaw/tools/portfolio_valuation`：组合估值工具
- `POST /api/v1/openclaw/tools/fund_brief`：基金简报工具
- `POST /api/v1/openclaw/tools/fund_history`：基金历史净值工具
- `POST /api/v1/openclaw/tools/market_overview`：大盘概览（指数 + 板块涨跌）
- `POST /api/v1/openclaw/tools/market_analysis`：综合分析（大盘 + 持仓 + 仓位）

## 数据来源策略

- 基金估算净值使用天天基金估算接口 `fundgz.1234567.com.cn/js/{fund_code}.js`
- 历史净值趋势使用天天基金 F10 接口 `api.fund.eastmoney.com/f10/lsjz`
- 基金基础信息使用基金代码列表 `fund.eastmoney.com/js/fundcode_search.js`
- 接口层统一做超时控制、缓存和异常包装

## 已知说明

- 基金历史趋势依赖天天基金与上游数据源，偶发超时属于外部数据波动
- 当前项目为单机 MVP，未引入鉴权、多用户和生产部署配置
- 前端错误提示已区分后端业务错误、超时错误和无响应错误

## 相关文档

- `doc/prds/基金净值估算.md`
- `doc/tech/基金净值估算技术方案.md`
- `doc/tech/MVP开发总结.md`