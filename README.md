# recsys-daily-papers

每日自动抓取 arXiv 最新推荐系统 & 营销增长相关论文，LLM 中文总结、分类、评分，输出日报到 GitHub Pages + 飞书群推送。

## 功能

- arXiv 多分类检索 + 关键词过滤
- Google Gemini 免费 LLM 中文摘要/分类/评分
- Semantic Scholar 引用数据补充
- 每日 Markdown 日报 + GitHub Pages 展示
- 飞书群机器人自动推送

## 运行方式

- **每日自动**: 北京时间 9:00 通过 GitHub Actions 定时触发
- **手动触发**: GitHub Actions → workflow_dispatch → Run workflow
- **本地试运行**: `pip install -r requirements.txt && cd src && python main.py --dry-run`

## 配置

在 GitHub Repo Settings → Secrets 中配置:
- `GEMINI_API_KEY` — Google Gemini API Key
- `FEISHU_WEBHOOK_URL` — 飞书群机器人 Webhook
