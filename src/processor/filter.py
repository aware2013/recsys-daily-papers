"""过滤模块：去重 + 关键词粗筛 + 质量过滤"""

import logging
from pathlib import Path
from typing import List, Set

import yaml

from src.config import PAPER_CATEGORIES, GROWTH_KEYWORDS
from src.models import Paper

logger = logging.getLogger(__name__)


def filter_papers(papers: List[Paper], processed_ids_file: str) -> List[Paper]:
    """去重 + 关键词相关性过滤 + 质量过滤"""
    # 1. 加载已处理 ID 去重
    processed_ids = _load_processed_ids(processed_ids_file)
    deduped = [p for p in papers if p.arxiv_id not in processed_ids]
    skipped = len(papers) - len(deduped)
    if skipped:
        logger.info(f"Dedup: skipped {skipped} already processed")

    # 2. 关键词相关性粗筛
    relevant = [p for p in deduped if _is_relevant(p)]
    filtered = len(deduped) - len(relevant)
    if filtered:
        logger.info(f"Keyword filter: removed {filtered} irrelevant")

    # 3. 质量过滤（摘要过短）
    quality = [p for p in relevant if len(p.abstract) >= 50]
    if len(relevant) - len(quality):
        logger.info(f"Quality filter: removed {len(relevant) - len(quality)} too-short abstracts")

    logger.info(f"Filter result: {len(papers)} total → {len(deduped)} dedup → {len(quality)} final")
    return quality


def _load_processed_ids(filepath: str) -> Set[str]:
    path = Path(filepath)
    if not path.exists():
        return set()
    try:
        data = yaml.safe_load(path.read_text()) or {}
        return set(data.get("ids", []))
    except Exception:
        logger.warning(f"Failed to load processed_ids from {filepath}")
        return set()


def save_processed_ids(filepath: str, ids: List[str]) -> None:
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_processed_ids(filepath)
    existing.update(ids)
    path.write_text(yaml.dump({"ids": sorted(existing), "total": len(existing)}, allow_unicode=True))


def _is_relevant(paper: Paper) -> bool:
    """检查论文是否与推荐系统或营销增长相关"""
    text = (paper.title + " " + paper.abstract).lower()

    # 遍历所有分类的关键词
    for keywords in PAPER_CATEGORIES.values():
        for kw in keywords:
            if kw.lower() in text:
                return True

    # 额外检查增长关键词
    for kw in GROWTH_KEYWORDS:
        if kw.lower() in text:
            return True

    return False
