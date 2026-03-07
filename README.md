# 基金透视 (Fund Insight) 🚀

根据基金最新季报十大重仓股 + 全市场股票实时行情，秒级估算基金当日实时涨幅。

本项目采用前后端分离架构，前端使用 **Next.js (App Router)** 提供现代化的暗黑风格 UI，后端基于 **FastAPI** 配合 **akshare** 实现高性能数据处理。

## 🌟 核心特性

- **秒级估值**: 基于内存缓存行情，响应时间 < 200ms。
- **大盘热度**: 实时展示全市场涨跌家数及涨跌停统计。
- **智能标签**: 根据交易状态自动切换“收盘”、“午间休市”等语义化标签。
- **自选管理**: 支持本地存储自选基金列表，一键追踪。
- **极致体验**: 针对移动端优化的紧凑布局，信息密度高。

## 🏗️ 项目结构

```text
fund/
├── backend/            # Python FastAPI 后端
│   ├── api.py          # RESTful 接口
│   ├── fund_estimation.py # 核心计算逻辑与异步缓存
│   └── requirements.txt # 后端依赖
├── frontend/           # Next.js 前端
│   ├── app/            # 页面、布局与样式
│   └── ...
├── README.md           # 项目主文档
├── DESIGN.md           # 架构设计与公式说明
└── DEPLOY.md           # 生产环境部署指南
```

## 🚀 快速开始

### 1. 后端启动 (Python 3.9+)

```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```
后端启动后会自动开启异步刷新线程，首次拉取行情约需 30s。

### 2. 前端启动 (Node.js 18+)

```bash
cd frontend
npm install
# 创建本地环境配置
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```
访问 `http://localhost:3000` 即可使用。

## 🧪 核心原理

1. **异步缓存**: 后端启动常驻线程，每 45 秒全量抓取 A 股实时行情。
2. **季报追溯**: 自动寻找基金最近三个年度内最新的十大重仓股数据。
3. **加权估算**: `估算涨幅 = Σ (重仓股涨幅 * 占比) / Σ (重仓股占比) * (总占比)`。

> 更多技术细节请参考 [DESIGN.md](./DESIGN.md)

## 📦 部署

- **前端**: 建议直接推送到 GitHub 并关联 **Vercel**。
- **后端**: 建议直接推送到 GitHub 并关联 **Zeabur** 或 **Railway**（支持 Python 常驻进程）。

> 详细部署手册见 [DEPLOY.md](./DEPLOY.md)

---

**免责声明**: 本项目仅供学习交流，数据源来自公开接口。估算结果受持仓滞后、盘中调仓等因素影响，仅供参考，不作为投资建议。
