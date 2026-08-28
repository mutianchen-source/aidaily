# AI 资讯日报 · GitHub 部署指南（全免费）

一个每天 08:00 自动抓取全网 AI 资讯、用 DeepSeek 大模型智能整理分类的资讯日报网站。
部署到 GitHub Pages 后，获得一个网址，任何人点开即看，且每天自动更新。

---

## 一、准备工作

1. 注册 GitHub 账号：https://github.com （免费）。
2. 新建仓库：右上角 `+` → `New repository`
   - Repository name 随便填，如 `ai-daily`
   - 选 **Public**（公开，免费才能用 Pages）
   - 其余默认，**不要**勾选初始化 README / .gitignore，创建空仓库。

---

## 二、推送代码到 GitHub

在你自己的 Mac 上打开「终端」，执行（把 `你的用户名` 和 `ai-daily` 换成你的）：

```bash
cd "/Users/qunxingshanyaoshi/Documents/AI CASE"
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/你的用户名/ai-daily.git
git push -u origin main
```

> 首次 push 会要求登录 GitHub，按提示在浏览器里授权即可。
> （`config.json` 已被 `.gitignore` 排除，你的 API key 不会上传，安全。）

---

## 三、配置密钥（Secrets）

1. 打开你的仓库 → **Settings** → **Secrets and variables** → **Actions**
2. 点 **New repository secret**，填：
   - Name：`DEEPSEEK_API_KEY`
   - Value：你的 DeepSeek key（`sk-` 开头那串）
3. 保存。

---

## 四、开启 GitHub Pages

1. 仓库 → **Settings** → **Pages**
2. **Build and deployment** → Source 选 **Deploy from a branch**
3. Branch 选 **main**，文件夹选 **/ (root)**，点 Save。
4. 等 1 分钟，页面上方会出现网址：`https://你的用户名.github.io/ai-daily/`
5. 浏览器打开这个网址，就能看到资讯日报了。

---

## 五、验证自动更新

- 每天 **北京时间 08:00**，GitHub Actions 会自动跑 `generate.py` 并更新数据。
- 想立刻看效果：仓库 → **Actions** → 左侧 **Daily Refresh** → **Run workflow** → 跑一次。
- 运行状态和日志都在 Actions 页面里看。

---

## 六、日常维护

- 想加/换新闻源：改 `generate.py` 顶部的 `FEEDS` 列表，push 上去即可。
- 想改刷新时间：改 `.github/workflows/daily-refresh.yml` 里的 `cron`（用的是 UTC 时间，北京时间 = UTC+8）。
- 想看每次运行日志：Actions → Daily Refresh → 某次运行 → 展开步骤。

---

## 常见问题

- **打开是空白/加载失败**：确认数据文件 `data/news.js` 已提交到仓库（本地先跑一次 `python3 generate.py` 再 push）。
- **Actions 报错**：多半是 Secrets 里的 key 没配或填错，去 Settings → Actions 检查。
