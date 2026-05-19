# 部署指南（Render + Vercel）

前后端分离：后端部署在 **Render**，前端部署在 **Vercel**。

---

## 部署步骤

### 1. 代码托管（GitHub）

确保代码已推送到 GitHub 仓库：`git@github.com:haisheng-zhang/FundAnalysis.git`

### 2. 后端部署（Render）

1. 打开 [Render](https://render.com/)，选择 **New → Web Service**，连接 GitHub 仓库
2. 参数配置：

| 参数 | 值 |
|------|----|
| Runtime | Python 3 |
| Root Directory | `backend` |
| Build Command | `pip3 install -r requirements.txt` |
| Start Command | `python3 -m uvicorn api:app --host 0.0.0.0 --port 10000` |
| Instance Type | Free |

3. 环境变量（AI 功能所需，前端当前为预约模式，可暂不填）：

| 变量 | 说明 |
|------|------|
| `LLM_AI_API_KEY` | OpenRouter API Key |
| `LLM_API_URL` | `https://openrouter.ai/api/v1/chat/completions` |
| `LLM_MODEL_NAME` | 推荐免费模型：`stepfun/step-3.5-flash:free` |

4. 部署完成后记录 URL，如 `https://xxx.onrender.com`

### 3. 前端部署（Vercel）

1. 打开 [Vercel](https://vercel.com/)，导入同一 GitHub 仓库
2. Root Directory 设置为 `frontend`，框架自动识别为 Next.js
3. 环境变量：

| 变量 | 值 |
|------|----|
| `NEXT_PUBLIC_API_URL` | 上一步的 Render URL（末尾不带 `/`） |
| `NEXT_PUBLIC_SALES_EMAIL` | 联系邮箱，如 `sean.zhang.fintech.edu@gmail.com` |

4. 点击 **Deploy**

### 4. 自定义域名（Namecheap → Vercel）

Vercel **Settings → Domains** 添加域名后，在 Namecheap Advanced DNS 添加：

| 类型 | 主机 | 值 |
|------|------|----|
| A | `@` | `76.76.21.21` |
| CNAME | `www` | `cname.vercel-dns.com.` |

---

## 本地运行

### 后端

```bash
cd backend
python3 -m venv ../venv
source ../venv/bin/activate      # Windows: ..\venv\Scripts\activate
pip install -r requirements.txt
python3 -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### 前端

```bash
cd frontend
npm install
# .env.local 已存在；若没有：
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
# 打开 http://localhost:3000
```

### 验证

```bash
# 后端健康检查
curl http://localhost:8000/api/hot-funds

# 基金估值
curl http://localhost:8000/api/fund/110011

# API 文档
open http://localhost:8000/docs
```

---

## 注意事项

- **冷启动**：Render 免费实例闲置 15 分钟后休眠，首次访问约需 30 秒唤醒（见下方保活方案）
- **CORS**：`api.py` 已配置 `allow_origins=["*"]`，生产环境可收窄为 Vercel 域名
- **内存缓存**：持仓缓存（24h）、热门基金缓存（每日）随进程重启清空，属正常现象
- **行情来源**：使用新浪财经批量接口，Render US 服务器可正常访问；东方财富批量接口在 US 服务器不可用
- **环境变量更新**：修改 `NEXT_PUBLIC_API_URL` 后需在 Vercel 重新部署才生效

---

## Render 免费版保活（Keep-Warm）

免费版闲置 15 分钟后休眠。在流量不大时可用外部定时 ping 保持唤醒，**无需升级付费**。

### 方案 A：UptimeRobot（推荐，零代码）

1. 注册 [UptimeRobot](https://uptimerobot.com/)（免费）
2. **Add New Monitor**：
   - Monitor Type: `HTTP(s)`
   - URL: `https://你的render域名.onrender.com/api/hot-funds`
   - Monitoring Interval: `5 minutes`
3. 保存即生效，24/7 自动 ping，Render 实例永久唤醒

**额度说明**：UptimeRobot 免费版支持最多 50 个 monitor，每5分钟 ping 一次，**无每日/每月 ping 次数限制**，24/7 全年运行无问题。Render 不会对外部 ping 保活有任何限制或投诉。

### 方案 B：GitHub Actions（代码化管理）

在仓库中创建 `.github/workflows/keep-warm.yml`：

```yaml
name: Keep Render Warm

on:
  schedule:
    - cron: '*/10 * * * *'  # 每10分钟，全天候
  workflow_dispatch:

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping backend
        run: curl -f https://你的render域名.onrender.com/api/hot-funds
```

> GitHub Actions 免费版每月 2000 分钟额度。每10分钟一次 = 每月约 4320 次，每次约1秒，共 ~72 分钟/月，远低于额度上限。

### 何时考虑升级 Render 付费（$7/月）

- 日活用户超过 50 人，冷启动影响体验
- AI 功能对外开放后，冷启动叠加 AI 响应时间（5-10s）不可接受
- 需要 SLA 保障的付费用户
