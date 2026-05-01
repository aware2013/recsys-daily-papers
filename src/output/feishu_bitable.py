"""飞书多维表格 Bitable — 推荐算法 & 营销增长两张表"""

import logging
import os
from typing import List

import httpx

from src.models import Paper

logger = logging.getLogger(__name__)

FEISHU_AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_BITABLE_API = "https://open.feishu.cn/open-apis/bitable/v1"

TABLE_FIELDS = [
    {"field_name": "日期", "type": 1},
    {"field_name": "序号", "type": 2},
    {"field_name": "分类", "type": 1},
    {"field_name": "中文标题", "type": 1},
    {"field_name": "英文标题", "type": 1},
    {"field_name": "评分", "type": 2},
    {"field_name": "核心贡献", "type": 1},
    {"field_name": "一句话推荐", "type": 1},
    {"field_name": "适用场景", "type": 1},
    {"field_name": "arXiv", "type": 15},
    {"field_name": "作者", "type": 1},
    {"field_name": "作者单位", "type": 1},
    {"field_name": "源码", "type": 15},  # url
]

TABLE_NAMES = {"推荐算法": "📊 推荐算法", "营销增长": "📈 营销增长"}


def sync_to_bitable(papers: List[Paper], bucket_map: dict, date_str: str) -> bool:
    """按桶分别写入两张表"""
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN", "")

    if not all([app_id, app_secret, app_token]):
        logger.warning("Feishu Bitable credentials not fully set, skipping")
        return False

    # 按桶分拆论文
    buckets: dict[str, list] = {}
    for p in papers:
        bucket = bucket_map.get(p.arxiv_id, "营销增长")
        buckets.setdefault(bucket, []).append(p)

    try:
        token = _get_tenant_token(app_id, app_secret)

        for bucket_name, bucket_papers in buckets.items():
            table_name = TABLE_NAMES.get(bucket_name, bucket_name)
            table_id = _ensure_table(token, app_token, table_name)
            records = _build_records(bucket_papers, date_str)
            _batch_create_records(token, app_token, table_id, records)
            logger.info(f"Bitable [{table_name}]: {len(records)} records appended")

        return True

    except Exception as e:
        logger.error(f"Bitable sync failed: {e}")
        return False


def _get_tenant_token(app_id: str, app_secret: str) -> str:
    resp = httpx.post(FEISHU_AUTH_URL, json={"app_id": app_id, "app_secret": app_secret}, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Feishu auth failed: {data}")
    return data["tenant_access_token"]


def _ensure_table(token: str, app_token: str, table_name: str) -> str:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    resp = httpx.get(
        f"{FEISHU_BITABLE_API}/apps/{app_token}/tables",
        headers=headers, params={"page_size": 20}, timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"List tables failed: {data}")

    for item in data.get("data", {}).get("items", []):
        if item.get("name") == table_name:
            logger.info(f"Bitable: using existing table '{table_name}'")
            _ensure_fields(token, app_token, item["table_id"], TABLE_FIELDS)
            return item["table_id"]

    resp = httpx.post(
        f"{FEISHU_BITABLE_API}/apps/{app_token}/tables",
        headers=headers,
        json={"table": {"name": table_name, "default_view_name": "全部论文", "fields": TABLE_FIELDS}},
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Create table failed: {data}")
    logger.info(f"Bitable: created new table '{table_name}'")
    return data["data"]["table_id"]


def _ensure_fields(token: str, app_token: str, table_id: str, fields: list):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = httpx.get(
        f"{FEISHU_BITABLE_API}/apps/{app_token}/tables/{table_id}/fields",
        headers=headers, params={"page_size": 30}, timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        return

    existing = {f["field_name"] for f in data.get("data", {}).get("items", [])}
    for field_def in fields:
        if field_def["field_name"] not in existing:
            httpx.post(
                f"{FEISHU_BITABLE_API}/apps/{app_token}/tables/{table_id}/fields",
                headers=headers, json=field_def, timeout=10.0,
            )
            logger.info(f"Bitable: added missing field '{field_def['field_name']}'")


def _build_records(papers: List[Paper], date_str: str) -> List[dict]:
    records = []
    for i, p in enumerate(papers, 1):
        records.append({
            "fields": {
                "日期": date_str,
                "序号": i,
                "分类": p.category or "其他",
                "中文标题": (p.cn_title or p.title)[:200],
                "英文标题": p.title[:300],
                "评分": round(p.rating, 1),
                "核心贡献": "\n".join(f"• {h}" for h in (p.highlights or []) if h)[:1000] or "暂无",
                "一句话推荐": p.one_sentence or "暂无",
                "适用场景": p.applicable_scenarios or "通用",
                "arXiv": {"link": p.abs_url, "text": p.arxiv_id},
                "作者": ", ".join(p.authors[:3]) + (f" et al.({len(p.authors)})" if len(p.authors) > 3 else ""),
                "作者单位": p.affiliations or "—",
                "源码": {"link": p.code_url, "text": "🔗 GitHub"} if p.code_url else None,
            }
        })
    return records


def _batch_create_records(token: str, app_token: str, table_id: str, records: List[dict]):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    batch_size = 20
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        resp = httpx.post(
            f"{FEISHU_BITABLE_API}/apps/{app_token}/tables/{table_id}/records/batch_create",
            headers=headers, json={"records": batch}, timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Batch create failed: {data}")
        logger.info(f"Bitable: batch {i // batch_size + 1} — {len(batch)} records written")
