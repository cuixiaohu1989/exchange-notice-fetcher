# 云端部署指南

将交易所通知爬虫部署到 GitHub Actions 云端运行，完全脱离本地电脑。

## 架构

```
GitHub Actions (云端, 每天北京时间 07:00)
  → main.py 爬取 6 家交易所通知
  → write_to_tdocs_cloud.py 通过腾讯文档 Open API 写入表格
  → git commit results.json + state/notices_state.json 到仓库
```

电脑关机也能照常运行。

---

## 步骤 1: 获取腾讯文档 API 凭据

### 1.1 注册开发者并创建应用

1. 打开 https://docs.qq.com/open/developers/
2. 使用微信或 QQ 登录，注册成为开发者
3. 创建第三方应用，回调地址设为 `https://docs.qq.com`
4. 审核通过后，在应用详情页获取 **Client ID**（应用ID）

### 1.2 获取 OAuth Token

在开发者平台的「API 调试」或授权页面，使用你的应用进行 OAuth 授权，获取以下 3 个值：

| 凭据 | 说明 | 获取方式 |
|---|---|---|
| **Client ID** | 应用 ID | 开发者平台 → 应用详情 |
| **Access Token** | API 访问令牌（30天有效） | OAuth 授权后获得 |
| **Open ID** | 用户唯一标识 | OAuth 授权后获得 |

> ⚠️ **Access Token 有效期约 30 天**，到期后需重新授权获取新 Token 并更新 GitHub Secrets。

---

## 步骤 2: 推送代码到 GitHub

```bash
cd exchange_notice_fetcher

# 初始化 git 仓库（如果还没有）
git init
git add .
git commit -m "Exchange notice crawler with cloud deployment"

# 添加远程仓库（替换为你的仓库地址）
git remote add origin https://github.com/你的用户名/exchange-notice-fetcher.git
git push -u origin main
```

---

## 步骤 3: 配置 GitHub Secrets

在 GitHub 仓库页面：

1. Settings → Secrets and variables → Actions
2. 点击 "New repository secret"
3. 逐个添加以下 3 个 Secret：

| Secret 名称 | 值 |
|---|---|
| `TDOC_ACCESS_TOKEN` | OAuth 授权获取的 Access Token |
| `TDOC_CLIENT_ID` | 应用的 Client ID |
| `TDOC_OPEN_ID` | OAuth 授权获取的 Open ID |

---

## 步骤 4: 测试运行

在 GitHub 仓库页面：

1. Actions → Exchange Notice Crawler
2. 点击 "Run workflow" → "Run workflow"
3. 等待执行完成（约 5-10 分钟）
4. 检查腾讯文档表格是否更新：https://docs.qq.com/sheet/DQk9LWHhFYXRpdmpz

---

## 文件说明

| 文件 | 说明 |
|---|---|
| `main.py` | 爬虫主入口，爬取 6 家交易所通知 |
| `scripts/write_to_tdocs_cloud.py` | 云端版写入脚本，使用腾讯文档 Open API sheetbook 端点 |
| `scripts/tdoc_oauth_helper.py` | OAuth 授权辅助脚本（可选，用于获取 refresh_token 长期方案） |
| `state/notices_state.json` | 去重状态文件，记录已写入通知和最后一行行号 |
| `.github/workflows/crawl.yml` | GitHub Actions 工作流配置 |

---

## 技术细节

### 腾讯文档 Open API 写入流程

```
1. 认证: 请求头携带 Access-Token / Client-Id / Open-Id
2. 内部 fileID: 300000000$BOKXxEativjs (URL编码后使用)
3. 写入端点: PUT /openapi/sheetbook/v2/{编码后的内部fileID}/values/{sheet_id}!{range}
4. 请求体: {"values": [["值1","值2",...], ...]}
```

### 去重机制

使用 `state/notices_state.json` 记录：
- `last_row`: 表格中最后一行数据的行号
- `written_keys`: 已写入通知的 (交易所, 日期, 标题) 三元组列表

每次运行时加载状态 → 过滤新通知 → 写入新行 → 更新状态 → git commit 回仓库。

---

## 注意事项

1. **Access Token 有效期约 30 天**：到期后 API 返回认证错误，需重新授权获取新 Token，更新 GitHub Secret `TDOC_ACCESS_TOKEN`
2. **GitHub Actions 免费额度**：公开仓库无限免费分钟数，私有仓库每月 2000 分钟（本项目每次约用 5-10 分钟）
3. **定时触发时间**：UTC 23:00 (周日~周四) = 北京时间 07:00 (周一~周五)。GitHub Actions 的 cron 可能延迟几分钟，属正常现象
4. **周末不运行**：爬虫在周末自动跳过（交易所不发布通知），不会写入任何数据
5. **原 WorkBuddy 自动化**：云端方案部署成功后，可以将本地的 WorkBuddy 自动化暂停或删除，避免重复运行

---

## Token 过期后的更新方法

当 Access Token 过期（约 30 天后），按以下步骤更新：

1. 重新在腾讯文档开发者平台进行 OAuth 授权，获取新的 Access Token
2. GitHub 仓库 → Settings → Secrets and variables → Actions
3. 更新 `TDOC_ACCESS_TOKEN` 的值为新 Token
4. 手动触发一次 workflow 验证是否正常

> 💡 **长期方案**：如需自动刷新 Token（避免每月手动操作），可提供应用的 Client Secret，实现 refresh_token 自动刷新流程。
