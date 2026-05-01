"""飞书 Webhook 通知 — 推荐算法 & 营销增长双通道推送"""

import logging
import os

import httpx

from src.config import FEISHU_MAX_PER_BUCKET
from src.models import DailyDigest, Paper

logger = logging.getLogger(__name__)


def send_notification(digest: DailyDigest) -> bool:
    """分别推送推荐算法和营销增长论文"""
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not webhook_url:
        logger.warning("FEISHU_WEBHOOK_URL not set, skipping push")
        return False

    recsys = [p for p in digest.papers if digest.bucket_map.get(p.arxiv_id) == "推荐算法"]
    growth = [p for p in digest.papers if digest.bucket_map.get(p.arxiv_id) == "营销增长"]

    ok = True
    if recsys:
        ok &= _send(webhook_url, digest.date, "🤖 推荐算法", recsys[:FEISHU_MAX_PER_BUCKET])
    if growth:
        ok &= _send(webhook_url, digest.date, "📈 营销增长", growth[:FEISHU_MAX_PER_BUCKET])

    return ok


def _send(webhook_url: str, date: str, label: str, papers: list) -> bool:
    stars = lambda r: "⭐" * max(1, int(r / 2)) if r else ""
    lines = [
        f"## {label} 论文日报 | {date}",
        "",
        f"今日精选 **{len(papers)}** 篇",
        "",
        "---",
        "",
    ]

    for i, p in enumerate(papers, 1):
        title = p.cn_title or p.title
        if len(title) > 80:
            title = title[:77] + "..."
        rating_text = f"{p.rating:.1f} {stars(p.rating)}" if p.rating else "—"
        lines.extend([
            f"### {i}. {title}",
            f"**分类**: {p.category or '其他'} ｜ **评分**: {rating_text}",
            f"**一句话**: {p.one_sentence or '暂无'}",
            f"[📄 arXiv]({p.abs_url}) | [📥 PDF]({p.pdf_url})",
            "",
        ])

    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"{label} 论文日报 | {date}",
                    "content": [[{"tag": "text", "text": line}] if not line.startswith("###") else [
                        {"tag": "text", "text": line}
                    ] for line in lines if line],
                }
            }
        },
    }

    # 转换为飞书 post 格式
    post_content = []
    for line in lines:
        if not line:
            continue
        if line.startswith("### "):
            post_content.append([{"tag": "text", "text": line[4:] + "\n"}])
        elif line.startswith("**"):
            post_content.append([{"tag": "text", "text": line + "\n"}])
        elif line.startswith("[📄"):
            post_content.append([{"tag": "text", "text": line + "\n"}])
        elif line.startswith("---"):
            post_content.append([{"tag": "text", "text": "———\n"}])
        elif line.startswith("## "):
            post_content.append([{"tag": "text", "text": line[3:] + "\n"}])
        else:
            post_content.append([{"tag": "text", "text": line + "\n"}])

    try:
        resp = httpx.post(webhook_url, json={
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": f"{label} 论文日报 | {date}",
                        "content": post_content,
                    }
                }
            },
        }, timeout=15.0)
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
