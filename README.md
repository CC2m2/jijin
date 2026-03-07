# 基金净值估算 MVP

基于技术方案实现的前后端分离 MVP。

## 技术栈

- 后端: FastAPI, SQLAlchemy, SQLite, akshare
- 前端: React, Vite, Ant Design, ECharts

## 功能范围

- 基金持仓新增、编辑、删除
- 基金基础信息查询
- 单基金估值
- 组合总览估值
- 估值失败项保留错误信息，不阻断整个组合计算

## 启动方式

### 1. 启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认访问 `http://127.0.0.1:8000/api/v1`。

## 核心接口

- `GET /api/v1/positions`
- `POST /api/v1/positions`
- `PUT /api/v1/positions/{id}`
- `DELETE /api/v1/positions/{id}`
- `GET /api/v1/funds/{fund_code}`
- `POST /api/v1/valuation/fund`
- `GET /api/v1/valuation/portfolio`

## 数据策略

- 优先使用 `ak.fund_value_estimation_em` 的估算净值
- 无估算数据时降级到 `ak.fund_open_fund_daily_em` 的最新净值
- 基金名称优先取估算数据，其次开放式基金日数据，再次基金基础信息和基金概况