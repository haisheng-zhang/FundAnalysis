# 设计文档

## 架构概览

前后端分离，后端 Render，前端 Vercel。

```
用户浏览器
    │
    ├── GET /api/fund/{code}        ← 估值 + 持仓
    ├── GET /api/search?q=          ← 基金搜索
    ├── GET /api/hot-funds          ← 热门基金
    └── GET /api/ai-analysis/{code} ← AI 分析（后端已就绪，前端暂为预约入口）
            │
        FastAPI (Render)
            │
            ├── AkShare ──────────── 基金持仓（季报）、基金搜索列表、热门排名
            └── 新浪财经 ─────────── 实时股票行情（批量，全品种含科创板）
```

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | Python / FastAPI |
| 数据源 | AkShare（持仓/搜索/排名）、新浪财经（行情） |
| AI 模型 | OpenRouter（DeepSeek/StepFun 等，后端已集成，前端待开放） |
| 数据处理 | Pandas |
| 前端框架 | Next.js 14 (App Router) |
| UI | 内联样式（暗黑主题）+ lucide-react 图标 |
| 部署 | Vercel（前端）+ Render（后端） |

## 关键设计决策

### 1. 行情数据源：新浪财经批量接口

`http://hq.sinajs.cn/list=sh600519,sz300308,...`

- 一次 HTTP 请求获取所有持仓股行情，无需并发
- 支持全品种（主板、创业板、科创板 688xxx）
- 非交易时段（午间、收盘后）返回最后成交价，涨跌幅仍有效
- 雪球接口（原方案）在 Render US 服务器对科创板股票返回 `'data'` KeyError，已弃用

### 2. 缓存策略

| 数据 | 缓存位置 | TTL | 说明 |
|------|----------|-----|------|
| 基金持仓（季报） | 内存 dict | 24小时 | 季报至多季度更新，无需频繁拉取 |
| 基金搜索列表 | 内存 DataFrame | 启动加载，不过期 | 26000+ 只基金代码+名称 |
| 热门基金 | 内存 list | 每日 | 按日期比对失效 |
| AI 分析报告 | 磁盘 JSON | 7天 | `data/ai_analysis/{code}.json` |

所有内存缓存随进程重启清空，无持久化依赖。

### 3. 估值计算公式

```
持仓权重_i  = 占净值比例_i / 100
贡献_i     = 持仓权重_i × 涨跌幅_i
估算涨幅   = Σ贡献_i / Σ持仓权重_i
```

仅基于季报披露的重仓股，未考虑：其余持仓、现金比例、盘中调仓。

### 4. 交易时间

A股交易时段（北京时间）：
- 上午：09:30 – 11:30
- 下午：13:00 – 15:00
- 工作日（周一至周五，不含节假日）

前端在交易时段内每60秒静默刷新当前基金估值；后端日志标注 `trading=True/False`。

### 5. AI 分析（后端已就绪，前端预约模式）

- 后端 `/api/ai-analysis/{code}` 完整实现，接入 OpenRouter
- 前端当前展示预约入口（¥19/年早鸟），不调用后端接口
- 开放时只需取消前端 `page.tsx` 中的注释块，无需改后端

## 目录结构

```
FundAnalysis/
├── backend/
│   ├── api.py                  # FastAPI 路由（4个端点）
│   ├── fund_estimation.py      # 核心逻辑：持仓、行情、估值、AI、热门基金
│   ├── prompt_config.py        # AI 提示词模板
│   ├── requirements.txt
│   └── data/
│       └── ai_analysis/        # AI 报告磁盘缓存（7天过期自动清理）
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # 主页（单页应用）
│   │   └── layout.tsx          # 全局布局
│   ├── .env.local.example
│   └── package.json
├── README.md
├── DESIGN.md
└── DEPLOY.md
```
