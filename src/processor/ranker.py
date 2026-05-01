"""排序评分模块"""

import math
from typing import List

from src.config import RATING_WEIGHTS, CITATION_LOG_BASE, MAX_CITATION_SCORE, PAPERS_PER_BUCKET
from src.models import Paper


def rank_papers(papers: List[Paper]) -> List[Paper]:
    """综合多维度评分后降序排列，截断到 PAPERS_PER_DIGEST 篇"""
    if not papers:
        return papers

    llm_scores = [p.rating for p in papers if p.rating > 0]
    avg_llm = sum(llm_scores) / len(llm_scores) if llm_scores else 5.0

    citations = [p.citation_count for p in papers]
    max_cite = max(citations) if citations else 1

    now_recent = 1.0

    for paper in papers:
        # 引用分：对数归一化
        cite_score = math.log(paper.citation_count + 1, CITATION_LOG_BASE) / math.log(
            max_cite + 1, CITATION_LOG_BASE
        ) * 10 if max_cite > 0 else 5.0

        # LLM 分归一化
        llm_norm = paper.rating if paper.rating > 0 else avg_llm

        # 时效性分（越新的论文分越高）
        recency = 0.8  # 48小时内的论文，时效分基础值
        if paper.published:
            hours_ago = (__import__("datetime").datetime.now(__import__("datetime").timezone.utc) - paper.published).total_seconds() / 3600
            recency = max(0.3, 1.0 - hours_ago / 72)  # 72小时内线性衰减

        # 新颖性分：标题中有 novel/new/first 等关键词加分
        novelty = _novelty_score(paper)

        w = RATING_WEIGHTS
        paper.rating = (
            w["llm_score"] * llm_norm
            + w["citation_score"] * cite_score
            + w["novelty_weight"] * novelty
            + w["recency_weight"] * recency * 10
        )

    papers.sort(key=lambda p: p.rating, reverse=True)
    return papers[:PAPERS_PER_BUCKET]


def _novelty_score(paper: Paper) -> float:
    novelty_keywords = ["novel", "new paradigm", "first", "state-of-the-art", "SOTA"]
    text = (paper.title + " " + paper.abstract[:500]).lower()
    count = sum(1 for kw in novelty_keywords if kw in text)
    return min(10.0, count * 2.5 + 5.0)
