# 从零部署到 GitHub Actions — 详细图文指南

> 本地代码已全部准备好并提交。以下步骤在 GitHub 网站上完成即可。

---

## 第一步：注册 GitHub 账号

1. 打开 https://github.com/signup
2. 输入邮箱、密码、用户名
3. 完成验证码验证
4. 选择 "Free" 免费计划
5. 完成注册

---

## 第二步：创建仓库

1. 登录后，点击右上角 **"+"** → **"New repository"**
2. 填写信息：
   - Repository name: `exchange-notice-fetcher`
   - Description: `交易所通知自动采集`
   - 选择 **Private**（私有，推荐）或 **Public**（公开）
   - ✅ 勾选 **"Add a README file"**
3. 点击 **"Create repository"**
4. 记下你的仓库地址，类似：`https://github.com/你的用户名/exchange-notice-fetcher`

---

## 第三步：创建 Personal Access Token（用于推送代码）

1. 点击右上角头像 → **Settings**
2. 左侧菜单最底部 → **Developer settings**
3. 左侧 → **Personal access tokens** → **Tokens (classic)**
4. 点击 **"Generate new token"** → **"Generate new token (classic)"**
5. 填写：
   - Note: `exchange-crawler`
   - Expiration: **90 days**（或自定义）
   - 勾选 **`repo`**（全部 repo 权限）
   - 勾选 **`workflow`**（更新 GitHub Actions 文件）
6. 点击页面底部 **"Generate token"**
7. ⚠️ **立即复制 Token**（页面关闭后无法再看到），格式类似：`ghp_xxxxxxxxxxxx`

---

## 第四步：在本地推送代码

打开终端（WorkBuddy 中我可以帮你执行），需要你提供：

1. **GitHub 用户名**
2. **刚才创建的 Token**
3. **仓库名**（默认 exchange-notice-fetcher）

我会执行：
```bash
git remote add origin https://你的用户名:你的Token@github.com/你的用户名/exchange-notice-fetcher.git
git push -u origin main
```

---

## 第五步：配置 3 个 Secrets

1. 打开你的仓库页面：`https://github.com/你的用户名/exchange-notice-fetcher`
2. 顶部标签页 → **Settings** → 左侧 **Secrets and variables** → **Actions**
3. 点击 **"New repository secret"**
4. 逐个添加以下 3 个：

### Secret 1
- Name: `TDOC_ACCESS_TOKEN`
- Value: 你的腾讯文档 access_token

### Secret 2
- Name: `TDOC_CLIENT_ID`
- Value: `1f69d76aeade4549b19e9827bdcf5ff4`

### Secret 3
- Name: `TDOC_OPEN_ID`
- Value: `57711ab47d26415096a45b59142d8f2f`

---

## 第六步：手动测试运行

1. 仓库页面 → 顶部 **Actions** 标签
2. 左侧选择 **"Exchange Notice Crawler"**
3. 点击右侧 **"Run workflow"** → **"Run workflow"**
4. 等待 5-10 分钟（黄色圆圈 = 运行中，绿色 ✓ = 成功，红色 ✗ = 失败）
5. 成功后检查腾讯文档表格是否有数据：https://docs.qq.com/sheet/DQk9LWHhFYXRpdmpz

---

## 后续

- **每天自动运行**：UTC 23:00 (周日~周四) = 北京时间 07:00 (周一~周五)
- **周末自动跳过**：交易所周末不发布通知
- **Token 有效期**：Access Token 约 30 天过期，届时更新 Secret `TDOC_ACCESS_TOKEN` 即可
- **本地电脑**：可以关机，完全在云端运行
