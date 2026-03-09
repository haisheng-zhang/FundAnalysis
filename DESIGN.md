# 设计说明

## 核心架构

项目采用前后端分离架构：

- **后端 (Backend)**: 基于 Python FastAPI，负责数据抓取、实时估值计算及 AI 分析生成。
- **前端 (Frontend)**: 基于 Next.js (App Router)，负责展示基金持仓、估算涨幅及 AI 深度报告。

## 技术栈

| 部分 | 技术 | 说明 |
|------|------|------|
| 后端框架 | Python (FastAPI) | 高性能异步 Web 框架 |
| 数据源 | AkShare / 雪球 API | 实时股票行情及基金持仓数据 |
| AI 模型 | DeepSeek R1 (via OpenRouter) | 基金深度分析与持仓解读 |
| 数据处理 | Pandas / ThreadPoolExecutor | 高效矩阵运算与并发数据抓取 |
| 前端框架 | Next.js (React) | 现代化的前端开发框架 |
| 样式/渲染 | Tailwind CSS / React Markdown | 响应式 UI 与富文本渲染 |

## 关键设计

### 1. 实时行情获取策略
  - 当用户请求某基金估值时，后端解析出其十大重仓股代码。
  - 使用 `ThreadPoolExecutor` (线程池) 并发请求这 10 只股票的实时行情。
  - **优势**: 响应速度快 (通常 < 300ms)，且不浪费 API 额度，仅查询用户关心的股票。
  - **交易时间感知**: 仅在 A 股交易时段调用实时接口，非交易时段返回静态数据或收盘数据。

### 2. AI 深度分析系统
- **触发机制**: 用户点击“AI 分析报告”按钮时触发。
- **缓存策略**:
  - **文件缓存**: 生成的报告存储在 `backend/data/ai_analysis/{fund_code}.json`。
  - **有效期**: 报告默认缓存 7 天。7 天内的请求直接返回缓存内容（响应 < 50ms）。
  - **过期清理**: 后台启动定时任务，每日凌晨自动清理过期文件。

### 3. 基金涨幅估算逻辑
- **数据获取**: 根据输入的基金代码，实时抓取该基金最新的季报前十大重仓股。
- **计算公式**: `基金估算涨幅 = Σ (重仓股涨跌幅 * 该股占净值比例) / Σ (前十大重仓股占净值比例) * (前十大重仓股总占比)`
  - *注：这是一种近似估算法，未考虑剩余持仓及盘中调仓。*

### 4. 前后端通信与部署
- **Render (后端)**: 部署 FastAPI 服务。
- **Vercel (前端)**: 部署 Next.js 应用，自动处理 HTTPS 和 CDN。
- **跨域 (CORS)**: 后端配置允许来自 Vercel 域名的跨域请求。

### 5. 扩展性设计
- **支付集成**: 预留了 Webhook 接口位置，未来可接入 Lemon Squeezy 实现高级会员功能 (如无限次 AI 分析)。

## 目录结构

```text
fund/
├── backend/            # 后端 Python 代码
│   ├── api.py          # FastAPI 入口与生命周期管理
│   ├── fund_estimation.py # 核心估值逻辑、AI生成与缓存管理
│   ├── prompt_config.py   # AI 提示词模板
│   ├── data/           # 本地数据持久化目录
│   │   └── ai_analysis/ # AI 报告 JSON 缓存
│   └── requirements.txt # 依赖列表
├── frontend/           # 前端 Next.js 代码
│   ├── app/            # 页面与布局
│   │   ├── page.tsx    # 主页逻辑
│   │   └── layout.tsx  # 全局布局
│   └── ...
├── README.md           # 项目总览
├── DESIGN.md           # 设计文档
└── DEPLOY.md           # 部署指南
```
