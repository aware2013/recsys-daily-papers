"""数据模型定义"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Paper:
    arxiv_id: str
    title: str
    authors: List[str] = field(default_factory=list)
    abstract: str = ""
    categories: List[str] = field(default_factory=list)
    published: Optional[datetime] = None
    updated: Optional[datetime] = None
    pdf_url: str = ""
    abs_url: str = ""

    # Semantic Scholar 补充
    citation_count: int = 0
    influential_citation_count: int = 0

    # LLM 处理结果 (中文)
    cn_title: str = ""
    cn_summary: str = ""
    category: str = ""
    highlights: List[str] = field(default_factory=list)
    rating: float = 0.0
    one_sentence: str = ""
    applicable_scenarios: str = ""


@dataclass
class DailyDigest:
    date: str
    total_candidates: int = 0
    after_filter: int = 0
    after_dedup: int = 0
    papers: List[Paper] = field(default_factory=list)
    generated_at: str = ""
    stats: dict = field(default_factory=dict)
