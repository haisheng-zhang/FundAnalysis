# 🚀 最终部署指南 (Render + Vercel)

本项目采用**前后端分离**架构。后端部署在 **Render**，前端部署在 **Vercel**，并绑定自定义域名 `eazyflow.xyz`。

---

## 📅 部署 Checklist (操作顺序)

### 第一步：代码托管 (GitHub)
- [x] 确保代码已推送到 GitHub 仓库：`git@github.com:haisheng-zhang/FundAnalysis.git`

### 第二步：后端部署 (Render)
1. **创建服务**: 访问 [Render](https://render.com/)，选择 **New** -> **Web Service**。
2. **连接仓库**: 授权并连接你的 GitHub 仓库。
3. **配置参数**:
   - **Name**: `fund-analysis-backend` (建议)
   - **Runtime**: `Python 3`
   - **Root Directory**: `backend` (如果仓库根目录下有 backend 文件夹)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api:app --host 0.0.0.0 --port 10000`
   - **Instance Type**: 选择 **Free**。
4. **获取域名**: 记录部署成功后的 URL (例如 `https://xxx.onrender.com`)。

### 第三步：前端部署 (Vercel)
1. **导入项目**: 访问 [Vercel](https://vercel.com/)，导入 GitHub 仓库。
2. **配置框架**: 自动识别为 **Next.js**。
3. **设置根目录**: 如果前端代码在 `frontend` 目录下，将 **Root Directory** 设置为 `frontend`。
4. **环境变量 (关键)**: 
   - 在 **Environment Variables** 中添加：
     - **Key**: `NEXT_PUBLIC_API_URL`
     - **Value**: `https://your-render-url.onrender.com` (填写第二步中获取的后端地址，末尾不要带 `/`)
5. **执行部署**: 点击 **Deploy**。

### 第四步：自定义域名配置 (Namecheap)

如果你拥有域名 `eazyflow.xyz` 并想将其指向 Vercel：

1. **Vercel 设置**:
   - 进入 Vercel 项目控制面板 -> **Settings** -> **Domains**。
   - 输入 `eazyflow.xyz` 并点击 **Add**。
2. **Namecheap DNS 配置**:
   - 登录 [Namecheap](https://www.namecheap.com/)，进入 **Domain List** -> **Manage** -> **Advanced DNS**。
   - 添加以下两条记录：
     - **Type**: `A Record` | **Host**: `@` | **Value**: `76.76.21.21` | **TTL**: `Automatic/1 min`
     - **Type**: `CNAME Record` | **Host**: `www` | **Value**: `cname.vercel-dns.com.` | **TTL**: `Automatic/1 min`
3. **等待生效**: DNS 生效可能需要几分钟到几小时（通常很快）。

---

## ⚠️ 常见问题与注意事项

- **后端冷启动**: Render 免费版在 15 分钟无活跃请求后会自动休眠。首次访问网页时，后端可能需要约 30 秒进行“热身”，期间页面可能会显示加载中或数据为空。
- **跨域 (CORS)**: 
  - 后端 `api.py` 中必须配置 `CORSMiddleware` 以允许 Vercel 域名或自定义域名访问。
  - 目前配置为 `allow_origins=["*"]` 以简化部署。
- **环境变量更新**: 如果后端 URL 发生变化，必须在 Vercel 的 Settings 中更新 `NEXT_PUBLIC_API_URL` 并**重新部署 (Redeploy)** 才会生效。
- **HTTPS**: Vercel 会自动为自定义域名配置 SSL 证书，无需手动操作。

---

## 🛠 维护与日志
- **查看后端日志**: 在 Render 控制面板的 **Logs** 标签页查看。
- **查看前端日志**: 在 Vercel 控制面板的 **Logs** 或 **Runtime Logs** 查看。
