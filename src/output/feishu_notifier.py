"""飞书 Webhook 通知模块"""

import logging
import os

import httpx

from src.config import FEISHU_MAX_PAPERS
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

    payload = _build_post_message(digest, top_papers)

    try:
        resp = httpx.post(webhook_url, json=payload, timeout=15.0)
        logger.info(f"Feishu response status={resp.status_code}, body={resp.text[:400]}")
        resp.raise_for_status()
        result = resp.json()
        code = result.get("StatusCode") or result.get("code") or 0
        msg = result.get("StatusMessage") or result.get("msg") or ""
        if code == 0:
            logger.info(f"Feishu push OK: {len(top_papers)} papers")
            return True
        else:
            logger.warning(f"Feishu push returned non-zero: code={code}, msg={msg}")
            return False
    except Exception as e:
        logger.error(f"Feishu push failed: {e}")
        return False


def _build_post_message(digest: DailyDigest, top_papers) -> dict:
    """构建飞书 post 富文本消息"""
    stars = lambda r: "⭐" * max(1, int(r / 2)) if r else ""

    content_lines = []
    # 标题行
    content_lines.append([{"tag": "text", "text": f"📢 论文日报 | {digest.date}\n"}])
    content_lines.append([{"tag": "text", "text": f"今日收录 {len(digest.papers)} 篇 | 来源: arXiv → 精选 {digest.after_dedup} 篇\n\n"}])

    for i, paper in enumerate(top_papers, 1):
        title = paper.cn_title or paper.title
        if len(title) > 80:
            title = title[:77] + "..."
        rating_text = f"{paper.rating:.1f} {stars(paper.rating)}" if paper.rating else "—"
        one_line = paper.one_sentence or "暂无简介"

        content_lines.append([
            {"tag": "text", "text": f"{i}. "},
            {"tag": "a", "text": title, "href": paper.abs_url},
            {"tag": "text", "text": f"\n   分类: {paper.category or '其他'} | 评分: {rating_text}\n   {one_line}\n\n"},
        ])

    return {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"论文日报 | {digest.date}",
                    "content": content_lines,
                }
            }
        },
    }
