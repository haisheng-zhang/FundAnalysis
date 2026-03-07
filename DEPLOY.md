# 🚀 最终部署指南 (Zeabur + Vercel)

本项目采用**前后端分离**架构。后端部署在 **Zeabur**，前端部署在 **Vercel**。两款工具均支持 GitHub 联动，**无需编写 GitHub Actions 文件**，推送到 GitHub 即可自动触发部署。

---

## 📅 部署 Checklist (操作顺序)

### 第一步：代码 Check-in
- [ ] 确保代码已推送到你的 GitHub 仓库。

### 第二步：后端部署 (Zeabur)
1. [ ] 访问 [Zeabur](https://zeabur.com/) 并使用 GitHub 账号登录。
2. [ ] 点击 **Create Project** -> **Deploy Service** -> **GitHub**。
3. [ ] 选择本项目的仓库，并指定 Root Directory 为 `backend`。
4. [ ] Zeabur 会自动识别 `requirements.txt` 并启动服务。
5. [ ] **生成域名**: 在该服务的 "Domain" 选项卡中，生成一个免费域名（如 `fund-api.zeabur.app`）。**记录下这个地址**。

### 第三步：前端部署 (Vercel)
1. [ ] 访问 [Vercel](https://vercel.com/) 并使用 GitHub 账号登录。
2. [ ] 点击 **Add New** -> **Project** -> **Import** 本项目仓库。
3. [ ] **重要配置**:
   - **Root Directory**: 设置为 `frontend`。
   - **Environment Variables**: 添加 `NEXT_PUBLIC_API_URL`。
   - **Value**: 填写刚才在 Zeabur 生成的后端地址（例如 `https://fund-api.zeabur.app`，**末尾不要带斜杠**）。
4. [ ] 点击 **Deploy**。

### 第四步：最终验证
1. [ ] 访问 Vercel 生成的前端链接。
2. [ ] 观察右上角是否显示大盘热度（若显示“连接中”，说明后端正在拉取初始数据，请等候 30s）。

---

## 💡 为什么不需要 GitHub Actions？

Zeabur 和 Vercel 内部已经集成了比 GitHub Actions 更轻量、更稳定的 CI/CD 流程：
1. **自动构建**: 只要你 `git push` 到主分支，它们会立即捕捉到代码变更并开始构建。
2. **无需秘钥**: 它们通过 GitHub App 权限直接访问仓库，不需要你在 GitHub Secrets 中配置 API Key。
3. **零配置部署**: 它们会自动分析项目类型（FastAPI / Next.js），自动安装依赖并分配端口。

## ⚠️ 特别注意
- **跨域 (CORS)**: 后端 `api.py` 默认已允许所有来源请求。如果部署后出现跨域问题，请检查前端环境变量地址是否拼写正确。
- **服务常驻**: Zeabur 的免费计划支持服务持续运行，这对于本项目的行情刷新线程非常重要。
