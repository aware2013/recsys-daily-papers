"""arXiv API 论文获取"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List

import arxiv

from src.config import ARXIV_CATEGORIES, SEARCH_QUERIES, GROWTH_KEYWORDS, LOOKBACK_HOURS, MAX_RESULTS_PER_CATEGORY, ARXIV_DELAY_SECONDS
from src.models import Paper

logger = logging.getLogger(__name__)


def fetch_papers() -> List[Paper]:
    """从 arXiv 获取最近论文，返回去重后的 Paper 列表"""
    all_papers: dict[str, Paper] = {}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    client = arxiv.Client(page_size=MAX_RESULTS_PER_CATEGORY, delay_seconds=ARXIV_DELAY_SECONDS, num_retries=3)

    for category, query in SEARCH_QUERIES.items():
        full_query = f"cat:{category} AND ({query})"
        logger.info(f"Searching arXiv: {full_query[:120]}...")

        try:
            search = arxiv.Search(
                query=full_query,
                max_results=MAX_RESULTS_PER_CATEGORY,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )

            for result in client.results(search):
                # 仅保留最近 N 小时内更新的论文
                updated = result.updated.replace(tzinfo=timezone.utc)
                if updated < cutoff:
                    continue

                if result.entry_id in all_papers:
                    continue

                arxiv_id = _extract_id(result.entry_id)
                paper = Paper(
                    arxiv_id=arxiv_id,
                    title=result.title.strip(),
                    authors=[a.name for a in result.authors],
                    abstract=result.summary.strip(),
                    categories=[c for c in result.categories],
                    published=result.published.replace(tzinfo=timezone.utc) if result.published else None,
                    updated=updated,
                    pdf_url=result.pdf_url,
                    abs_url=result.entry_id,
                )
                all_papers[arxiv_id] = paper

                logger.debug(f"  Found: {arxiv_id} — {result.title[:80]}")

        except Exception as e:
            logger.error(f"arXiv query failed for category={category}: {e}")

    # 额外用 GROWTH_KEYWORDS 在 cs.LG 中搜索营销增长论文
    for kw in GROWTH_KEYWORDS:
        try:
            search = arxiv.Search(
                query=f'cat:cs.LG AND abs:"{kw}"',
                max_results=20,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )
            for result in client.results(search):
                updated = result.updated.replace(tzinfo=timezone.utc)
                if updated < cutoff:
                    continue
                arxiv_id = _extract_id(result.entry_id)
                if arxiv_id in all_papers:
                    continue
                paper = Paper(
                    arxiv_id=arxiv_id,
                    title=result.title.strip(),
                    authors=[a.name for a in result.authors],
                    abstract=result.summary.strip(),
                    categories=[c for c in result.categories],
                    published=result.published.replace(tzinfo=timezone.utc) if result.published else None,
                    updated=updated,
                    pdf_url=result.pdf_url,
                    abs_url=result.entry_id,
                )
                all_papers[arxiv_id] = paper
        except Exception as e:
            logger.warning(f"Growth keyword search failed for '{kw}': {e}")

    papers = list(all_papers.values())
    logger.info(f"arXiv fetch complete: {len(papers)} papers (lookback={LOOKBACK_HOURS}h)")
    return papers


def _extract_id(entry_id: str) -> str:
    """从 arXiv entry_id 提取纯 ID"""
    # http://arxiv.org/abs/2301.12345v2 → 2301.12345
    return entry_id.split("/")[-1].split("v")[0]
