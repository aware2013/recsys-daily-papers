"""Semantic Scholar API — 补充引用数据，失败不阻塞主流程"""

import logging
import httpx
from typing import List

from src.models import Paper

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"


def enrich_papers(papers: List[Paper]) -> List[Paper]:
    """批量获取 Semantic Scholar 引用数据，失败时静默降级"""
    if not papers:
        return papers

    arxiv_ids = [p.arxiv_id for p in papers]
    url = f"{SEMANTIC_SCHOLAR_BASE}/paper/batch"

    try:
        payload = {"ids": [f"ArXiv:{aid}" for aid in arxiv_ids]}
        fields = "citationCount,influentialCitationCount,externalIds"
        resp = httpx.post(
            url,
            json=payload,
            params={"fields": fields},
            timeout=30.0,
        ).raise_for_status()
    except Exception as e:
        logger.warning(f"Semantic Scholar API failed (non-blocking): {e}")
        return papers

    data_list = resp.json()
    if not isinstance(data_list, list):
        return papers

    for i, item in enumerate(data_list):
        if item is None:
            continue
        if i < len(papers):
            papers[i].citation_count = item.get("citationCount", 0) or 0
            papers[i].influential_citation_count = item.get("influentialCitationCount", 0) or 0

    logger.info(f"Semantic Scholar: enriched {len(papers)} papers")
    return papers
