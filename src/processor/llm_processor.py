"""DeepSeek LLM 处理器：中文摘要、分类、评分。失败时降级为关键词方案"""

import json
import logging
import os
import re
import time
from typing import List

import httpx

from src.config import (
    GEMINI_TEMPERATURE,
    GEMINI_MAX_TOKENS,
    SYSTEM_PROMPT,
    PAPER_CATEGORIES,
    FALLBACK_CATEGORY,
)
from src.models import Paper

logger = logging.getLogger(__name__)

DEEPSEEK_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"
MAX_RETRIES = 3
CALL_DELAY = 1.0  # DeepSeek 不限流，短间隔即可


def process_papers(papers: List[Paper]) -> List[Paper]:
    """主入口：调用 LLM 处理论文列表"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key or not papers:
        if not api_key:
            logger.warning("DEEPSEEK_API_KEY not set, using keyword fallback")
        return _fallback_process(papers)

    results = []
    success_count = 0
    fail_count = 0

    for paper in papers:
        result = _call_with_retry(api_key, paper)
        if result:
            results.append(_apply_result(paper, result))
            success_count += 1
        else:
            results.append(_fallback_single(paper))
            fail_count += 1
        time.sleep(CALL_DELAY)

    logger.info(f"DeepSeek processed: {success_count} succeeded, {fail_count} fallback")
    return results


def _call_with_retry(api_key: str, paper: Paper) -> dict | None:
    for attempt in range(MAX_RETRIES):
        try:
            return _call_deepseek(api_key, paper)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = 3.0 * (2 ** attempt)
                logger.warning(
                    f"DeepSeek {paper.arxiv_id}: attempt {attempt + 1} failed, "
                    f"retrying in {wait:.1f}s... ({e})"
                )
                time.sleep(wait)
            else:
                logger.error(f"DeepSeek {paper.arxiv_id}: all attempts failed: {e}")
                return None
    return None


def _call_deepseek(api_key: str, paper: Paper) -> dict:
    user_text = f"标题: {paper.title}\n摘要: {paper.abstract}"
    prompt = f"{SYSTEM_PROMPT}\n\n论文信息：\n{user_text}"

    resp = httpx.post(
        f"{DEEPSEEK_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": GEMINI_TEMPERATURE,
            "max_tokens": GEMINI_MAX_TOKENS,
            "stream": False,
        },
        timeout=60.0,
    )
    resp.raise_for_status()

    data = resp.json()
    text = data["choices"][0]["message"]["content"].strip()

    # 提取 JSON
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        return json.loads(json_match.group(0))
    return json.loads(text)


def _apply_result(paper: Paper, result: dict) -> Paper:
    paper.cn_title = result.get("cn_title", "")
    paper.cn_summary = result.get("cn_summary", "")
    paper.category = result.get("category", FALLBACK_CATEGORY)
    paper.highlights = result.get("highlights", [])
    paper.rating = float(result.get("rating", 5.0))
    paper.one_sentence = result.get("one_sentence", "")
    paper.applicable_scenarios = result.get("applicable_scenarios", "")
    # LLM 推断的作者单位优先于 S2 数据
    llm_affil = result.get("affiliations", "")
    if llm_affil and llm_affil != "未知":
        paper.affiliations = llm_affil
    return paper


def _fallback_process(papers: List[Paper]) -> List[Paper]:
    return [_fallback_single(p) for p in papers]


def _fallback_single(paper: Paper) -> Paper:
    paper.cn_title = paper.title
    sentences = paper.abstract.split(". ")
    paper.cn_summary = ". ".join(sentences[:2]).rstrip(".") + "."
    paper.category = _classify_by_keywords(paper)
    paper.highlights = []
    kw_count = len(_extract_matched_keywords(paper))
    paper.rating = min(7.0, 3.0 + kw_count * 0.8)
    paper.one_sentence = "暂无LLM摘要（关键词降级模式）"
    paper.applicable_scenarios = ""
    return paper


def _classify_by_keywords(paper: Paper) -> str:
    text = (paper.title + " " + paper.abstract).lower()
    best_cat = FALLBACK_CATEGORY
    best_count = 0
    for cat, keywords in PAPER_CATEGORIES.items():
        count = sum(1 for kw in keywords if kw.lower() in text)
        if count > best_count:
            best_count = count
            best_cat = cat
    return best_cat


def _extract_matched_keywords(paper: Paper) -> List[str]:
    text = (paper.title + " " + paper.abstract).lower()
    matched = []
    for keywords in PAPER_CATEGORIES.values():
        for kw in keywords:
            if kw.lower() in text:
                matched.append(kw)
    return matched
