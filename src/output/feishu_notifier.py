"""飞书 Webhook 通知 — 推荐算法 & 营销增长双通道推送"""

import logging
import os

import httpx

from src.config import FEISHU_MAX_PER_BUCKET
from src.models import DailyDigest

logger = logging.getLogger(__name__)

COLORS = {"推荐算法": "blue", "营销增长": "green"}


def send_notification(digest: DailyDigest) -> bool:
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not webhook_url:
        logger.warning("FEISHU_WEBHOOK_URL not set, skipping push")
        return False

    recsys = [p for p in digest.papers if digest.bucket_map.get(p.arxiv_id) == "推荐算法"]
    growth = [p for p in digest.papers if digest.bucket_map.get(p.arxiv_id) == "营销增长"]

    ok = True
    if recsys:
        ok &= _send_card(webhook_url, digest.date, "🤖 推荐算法", recsys[:FEISHU_MAX_PER_BUCKET], "blue")
    if growth:
        ok &= _send_card(webhook_url, digest.date, "📈 营销增长", growth[:FEISHU_MAX_PER_BUCKET], "green")

    return ok


def _send_card(webhook_url: str, date: str, label: str, papers: list, color: str) -> bool:
    stars = lambda r: "⭐" * max(1, int(r / 2)) if r else ""

    md = f"**{label} 论文日报 | {date}**\n\n今日精选 **{len(papers)}** 篇\n\n---\n\n"

    for i, p in enumerate(papers, 1):
        title = p.cn_title or p.title
        if len(title) > 60:
            title = title[:57] + "..."
        rating_text = f"{p.rating:.1f} {stars(p.rating)}" if p.rating else "—"
        affil = f" | {p.affiliations}" if p.affiliations and p.affiliations != "—" else ""
        code_line = f"\n📦 [源码]({p.code_url})" if p.code_url else ""
        md += (
            f"**{i}. [{title}]({p.abs_url})**\n"
            f"{p.category or '其他'} ｜ 评分 {rating_text}{affil}{code_line}\n"
            f"{p.one_sentence or '暂无简介'}\n\n"
        )

    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{label} 论文日报 | {date}"},
                "template": color,
            },
            "elements": [
                {"tag": "markdown", "content": md},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": f"每日 {len(papers)} 篇精选 · Powered by arXiv + DeepSeek"}]},
            ],
        },
    }

    try:
        resp = httpx.post(webhook_url, json=payload, timeout=15.0)
        logger.info(f"Feishu [{label}] status={resp.status_code}, body={resp.text[:200]}")
        resp.raise_for_status()
        result = resp.json()
        code = result.get("StatusCode") or result.get("code") or 0
        if code == 0:
            logger.info(f"Feishu push OK: [{label}] {len(papers)} papers")
            return True
        else:
            logger.warning(f"Feishu push [{label}] failed: {result}")
            return False
    except Exception as e:
        logger.error(f"Feishu push [{label}] error: {e}")
        return False
