"""飞书多维表格 Bitable 写入模块"""

import json
import logging
import os
from typing import List

import httpx

from src.models import Paper

logger = logging.getLogger(__name__)

FEISHU_AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_BITABLE_API = "https://open.feishu.cn/open-apis/bitable/v1"


def sync_to_bitable(papers: List[Paper], date_str: str) -> bool:
    """将论文列表写入飞书多维表格"""
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN", "")

    if not all([app_id, app_secret, app_token]):
        logger.warning("Feishu Bitable credentials not fully set, skipping")
        return False

    try:
        token = _get_tenant_token(app_id, app_secret)
        table_id = _ensure_table(token, app_token, date_str)

        records = _build_records(papers, date_str)
        _batch_create_records(token, app_token, table_id, records)

        logger.info(f"Bitable: {len(records)} records written to table {table_id}")
        return True

    except Exception as e:
        logger.error(f"Bitable sync failed: {e}")
        return False


def _get_tenant_token(app_id: str, app_secret: str) -> str:
    resp = httpx.post(
        FEISHU_AUTH_URL,
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Feishu auth failed: {data}")
    return data["tenant_access_token"]


def _ensure_table(token: str, app_token: str, date_str: str) -> str:
    """查找今日表格，不存在则创建"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 列出现有表格
    resp = httpx.get(
        f"{FEISHU_BITABLE_API}/apps/{app_token}/tables",
        headers=headers,
        params={"page_size": 20},
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"List tables failed: {data}")

    table_name = f"论文日报 {date_str}"

    for item in data.get("data", {}).get("items", []):
        if item.get("name") == table_name:
            return item["table_id"]

    # 创建新表
    resp = httpx.post(
        f"{FEISHU_BITABLE_API}/apps/{app_token}/tables",
        headers=headers,
        json={
            "table": {
                "name": table_name,
                "default_view_name": "全部论文",
                "fields": [
                    {"field_name": "序号", "type": 2},  # number
                    {"field_name": "分类", "type": 3},  # text (暂用文本，首次运行后可改成单选)
                    {"field_name": "中文标题", "type": 1},  # text
                    {"field_name": "英文标题", "type": 1},  # text
                    {"field_name": "评分", "type": 2},  # number
                    {"field_name": "核心贡献", "type": 1},  # text
                    {"field_name": "一句话推荐", "type": 1},  # text
                    {"field_name": "适用场景", "type": 1},  # text
                    {"field_name": "arXiv", "type": 15},  # url
                    {"field_name": "引用数", "type": 2},  # number
                    {"field_name": "作者", "type": 1},  # text
                    {"field_name": "作者单位", "type": 1},  # text
                ],
            }
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Create table failed: {data}")
    return data["data"]["table_id"]


def _build_records(papers: List[Paper], date_str: str) -> List[dict]:
    records = []
    for i, p in enumerate(papers, 1):
        records.append({
            "fields": {
                "序号": i,
                "分类": p.category or "其他",
                "中文标题": (p.cn_title or p.title)[:200],
                "英文标题": p.title[:300],
                "评分": round(p.rating, 1),
                "核心贡献": "\n".join(f"• {h}" for h in (p.highlights or []) if h)[:1000] or "暂无",
                "一句话推荐": p.one_sentence or "暂无",
                "适用场景": p.applicable_scenarios or "通用",
                "arXiv": {
                    "link": p.abs_url,
                    "text": p.arxiv_id,
                },
                "引用数": p.citation_count,
                "作者": ", ".join(p.authors[:3]) + (f" et al.({len(p.authors)})" if len(p.authors) > 3 else ""),
                "作者单位": p.affiliations or "—",
            }
        })
    return records


def _batch_create_records(token: str, app_token: str, table_id: str, records: List[dict]):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 分批写入，每批 20 条
    batch_size = 20
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        resp = httpx.post(
            f"{FEISHU_BITABLE_API}/apps/{app_token}/tables/{table_id}/records/batch_create",
            headers=headers,
            json={"records": batch},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Batch create failed: {data}")
        logger.info(f"Bitable: batch {i // batch_size + 1} — {len(batch)} records written")
