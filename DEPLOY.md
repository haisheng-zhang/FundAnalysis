# 🚀 最终部署指南（Render + Vercel）

本项目采用**前后端分离**架构：后端部署在 **Render**，前端部署在 **Vercel**，并支持绑定自定义域名（例如 `eazyflow.xyz`）。

---

## 📅 部署检查清单（建议顺序）

### 第一步：代码托管（GitHub）
- [x] 确保代码已推送到 GitHub 仓库：`git@github.com:haisheng-zhang/FundAnalysis.git`

### 第二步：后端部署（Render）
1. 创建服务：打开 [Render](https://render.com/)，选择 **New** -> **Web Service**。
2. 连接仓库：授权并连接上述 GitHub 仓库。
3. 参数配置：
   - Name (服务名称): `fund-analysis-backend`
   - Runtime (运行环境): `Python 3`
   - Root Directory (根目录): `backend`
   - Build Command (构建命令): `pip3 install -r requirements.txt`
   - Start Command (启动命令): `python3 -m uvicorn api:app --host 0.0.0.0 --port 10000`
   - Instance Type (实例类型): 选择 **Free**
4. 获取域名：记录成功部署后的 URL（如 `https://xxx.onrender.com`）。

后端环境变量（必填）：
- `LLM_AI_API_KEY` = 你的 OpenRouter 密钥
- `LLM_API_URL` = `https://openrouter.ai/api/v1/chat/completions`
- `LLM_MODEL_NAME` = `deepseek/deepseek-r1`
- `顶流模型：OpenAI，Claude，DeepSeek等价格不一，都有好有差，根据自己的需求选择`
- `Google 的模型相对便宜，返回质量和速度以及限流需要测试`
- `MVP阶段我们从免费model开始，根据用户量选择是否升级到付费model`
- `比较好的免费model(没有限流，返回效果不错），试过了不错的： `
- `stepfun/step-3.5-flash:free：长，专业，偶尔会有问题，不返回结果，但是问题不大`
- `arcee-ai/trinity-large-preview:free，短，还行`


### 第三步：前端部署（Vercel）
1. 导入项目：打开 [Vercel](https://vercel.com/)，选择 **Import Git Repository**。
2. 框架识别：自动识别为 **Next.js**。
3. 设置根目录：如果前端代码在 `frontend` 目录，配置 **Root Directory** (根目录) 为 `frontend`。
4. 环境变量：
   - `NEXT_PUBLIC_API_URL` = `https://你的后端域名.onrender.com`（末尾不带 `/`）
   - `NEXT_PUBLIC_SALES_EMAIL` = `sean.zhang.fintech.edu@gmail.com`
5. 部署：点击 **Deploy**。

### 第四步：自定义域名（Namecheap）

如果你拥有域名 `eazyflow.xyz` 并希望指向 Vercel：

1. Vercel 设置：
   - 进入项目 **Settings** -> **Domains**
   - 输入 `eazyflow.xyz` 并点击 **Add**
2. Namecheap DNS 配置：
   - 登录 [Namecheap](https://www.namecheap.com/)，进入 **Domain List** -> **Manage** -> **Advanced DNS**
   - 添加如下两条记录：
     - 类型：`A` | 主机：`@` | 值：`76.76.21.21` | TTL：`Automatic/1 min`
     - 类型：`CNAME` | 主机：`www` | 值：`cname.vercel-dns.com.` | TTL：`Automatic/1 min`
3. 等待生效：通常几分钟内完成（也可能更长）。

---

## ⚠️ 常见问题与注意事项

- **后端冷启动**：Render 免费实例闲置约 15 分钟会休眠，首次访问可能需要约 30 秒“唤醒”，期间页面可能显示加载或空数据。
- **跨域（CORS）**：
  - 后端 `api.py` 已配置 `CORSMiddleware` 允许跨域（当前为 `allow_origins=["*"]`）
- **环境变量更新**：后端域名变更后，需在 Vercel 更新 `NEXT_PUBLIC_API_URL` 并 **重新部署** 生效。
- **HTTPS**：Vercel 会自动为自定义域名配置 SSL，无需手动操作。

---

## 🛠 维护与日志
- **后端日志**：Render 控制台 **Logs** 标签查看
- **前端日志**：Vercel 控制台 **Logs / Runtime Logs** 查看

---

## 🧪 本地测试说明

### 前端（Next.js）
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
# 打开 http://localhost:3000
```

### 后端（FastAPI）
```bash
cd backend
python3 -m venv ../venv
source ../venv/bin/activate
pip install -r requirements.txt
# 建议将密钥作为启动命令前缀传入，避免热重载环境丢失
LLM_AI_API_KEY=你的key LLM_API_URL=https://openrouter.ai/api/v1/chat/completions LLM_MODEL_NAME=deepseek/deepseek-r1 \
python3 -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### 端到端验证
- 打开 `http://localhost:8000/api/debug/version`，确认 Header `X-API-BUILD` 存在且 build_id 正确
- 前端点击“AI 分析报告”，后端终端应打印 `[REQ]` 与 `[api_ai_analysis]` 两条日志
- 打开 http://localhost:8000/docs 查看 API 文档