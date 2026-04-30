"""飞书 Webhook 通知模块"""

import json
import logging
import os

import httpx

from src.config import FEISHU_MAX_PAPERS, FEISHU_MESSAGE_CARD_TITLE, FEISHU_MESSAGE_CARD_COLOR
from src.models import DailyDigest

logger = logging.getLogger(__name__)


def send_notification(digest: DailyDigest) -> bool:
    """向飞书群发送论文日报消息"""
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not webhook_url:
        logger.warning("FEISHU_WEBHOOK_URL not set, skipping push")
        return False

    top_papers = digest.papers[:FEISHU_MAX_PAPERS]
    if not top_papers:
        logger.info("No papers to push")
        return False

    content = _build_markdown(digest, top_papers)
    payload = {"msg_type": "interactive", "card": _build_card(content, digest)}

    try:
        resp = httpx.post(webhook_url, json=payload, timeout=15.0)
        resp.raise_for_status()
        result = resp.json()
        if result.get("StatusCode") == 0 or result.get("code") == 0:
            logger.info(f"Feishu push OK: {len(top_papers)} papers")
            return True
        else:
            logger.warning(f"Feishu push returned: {result}")
            return False
    except Exception as e:
        logger.error(f"Feishu push failed: {e}")
        return False


def _build_markdown(digest: DailyDigest, top_papers) -> str:
    stars = lambda r: "⭐" * max(1, int(r / 2)) if r else ""
    lines = [
        f"## {FEISHU_MESSAGE_CARD_TITLE} | {digest.date}",
        "",
        f"今日共收录 **{len(digest.papers)}** 篇论文 ｜ arXiv 来源: {digest.total_candidates} → 精选: {digest.after_dedup} 篇",
        "",
        "---",
        "",
    ]

    for i, paper in enumerate(top_papers, 1):
        rating_text = f"{paper.rating:.1f} {stars(paper.rating)}" if paper.rating else "—"
        lines.extend([
            f"### {i}. {paper.cn_title or paper.title}",
            f"**分类**: {paper.category or '其他'} ｜ **评分**: {rating_text}",
            f"**一句话**: {paper.one_sentence or '暂无'}",
            f"[📄 arXiv]({paper.abs_url}) | [📥 PDF]({paper.pdf_url})",
            "",
        ])

    repo_url = os.environ.get("GITHUB_REPOSITORY", "")
    if repo_url:
        lines.append(f"[📖 全部详情](https://github.com/{repo_url}/tree/main/papers)")

    return "\n".join(lines)


def _build_card(markdown_content: str, digest: DailyDigest) -> dict:
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"论文日报 | {digest.date}"},
            "template": FEISHU_MESSAGE_CARD_COLOR,
        },
        "elements": [
            {"tag": "markdown", "content": markdown_content},
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": f"🤖 自动生成于 {digest.generated_at} | Powered by arXiv + Gemini"}
                ],
            },
        ],
    }
