# 每日股票复盘报告

自动生成、每日更新的股票复盘 Web 应用。前端复刻"主题卡片 + 雷达评分 + 证据表 + 事件日历 + 关联图谱"格式，
后端由 GitHub Actions 每日收盘后自动抓取行情并提交数据，GitHub Pages 自动发布。

## 技术栈
- 前端：原生 HTML/CSS/JS（零依赖，Pages 直接托管）
- 数据：AkShare（东方财富）→ 指数 / 涨跌停 / 板块资金流
- 自动化：GitHub Actions cron + git-auto-commit
- 可选 AI 总结：DeepSeek API

## GitHub Desktop 部署步骤（只需一次）
1. 安装并登录 [GitHub Desktop](https://desktop.github.com/)
2. File → New repository → 名称填 `stock-review-app` → Create repository（选择本地路径）
3. 把本项目的所有文件复制进该仓库文件夹
4. 回到 GitHub Desktop → 看到变更列表 → 填写 Commit message → 点 Commit to main
5. 点右上角 **Publish repository** 推送到 GitHub
6. 打开仓库网页 → Settings → Pages → Source 选 "Deploy from a branch" → Branch 选 `main` / `(root)` → Save
7. 等待 1~2 分钟，访问 `https://<你的用户名>.github.io/stock-review-app/`

## 启用每日自动更新
- 首次推送后，打开仓库的 Actions 页面（如提示需 Enable，点一下）
- 之后每个交易日 16:40（北京时间）自动抓取并更新，无需任何操作
- 也可以手动触发：Actions → 每日股票复盘自动更新 → Run workflow

## 可选：启用 AI 今日小结
仓库 Settings → Secrets and variables → Actions → New repository secret
- Name: `DEEPSEEK_API_KEY`
- Value: 你的 DeepSeek API Key（https://platform.deepseek.com）

## 目录结构
...

## 免责声明
本应用仅供学习研究，不构成任何投资建议。
