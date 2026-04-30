"""Gemini LLM 处理器：中文摘要、分类、评分。失败时降级为关键词方案"""

import json
import logging
import os
import asyncio
import re
from typing import List

from src.config import (
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    GEMINI_MAX_TOKENS,
    GEMINI_RPM_LIMIT,
    GEMINI_BATCH_SIZE,
    SYSTEM_PROMPT,
    PAPER_CATEGORIES,
    FALLBACK_CATEGORY,
)
from src.models import Paper

logger = logging.getLogger(__name__)


def process_papers(papers: List[Paper]) -> List[Paper]:
    """主入口：调用 LLM 处理论文列表"""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key or not papers:
        if not api_key:
            logger.warning("GEMINI_API_KEY not set, using keyword fallback")
        return _fallback_process(papers)

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        results = []

        for i in range(0, len(papers), GEMINI_BATCH_SIZE):
            batch = papers[i : i + GEMINI_BATCH_SIZE]
            for paper in batch:
                try:
                    result = _call_gemini(client, paper)
                    results.append(_apply_result(paper, result))
                except Exception as e:
                    logger.warning(f"Gemini failed for {paper.arxiv_id}: {e}")
                    results.append(_fallback_single(paper))

        logger.info(f"LLM processed: {len(papers)} papers")
        return results

    except ImportError:
        logger.warning("google-genai not installed, using keyword fallback")
        return _fallback_process(papers)
    except Exception as e:
        logger.error(f"Gemini API unreachable: {e}, using keyword fallback")
        return _fallback_process(papers)


def _call_gemini(client, paper: Paper) -> dict:
    user_text = f"标题: {paper.title}\n摘要: {paper.abstract}"
    prompt = SYSTEM_PROMPT.replace("{titles_and_abstract}", user_text)
    # fallback: use as normal chat
    if "{titles_and_abstract}" in prompt:
        prompt = f"{SYSTEM_PROMPT}\n\n论文信息：\n{user_text}"

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "temperature": GEMINI_TEMPERATURE,
            "max_output_tokens": GEMINI_MAX_TOKENS,
        },
    )

    text = response.text.strip()
    # 提取 JSON（可能被 markdown 包裹）
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        return json.loads(json_match.group(0))

    # 尝试直接解析
    return json.loads(text)


def _apply_result(paper: Paper, result: dict) -> Paper:
    paper.cn_title = result.get("cn_title", "")
    paper.cn_summary = result.get("cn_summary", "")
    paper.category = result.get("category", FALLBACK_CATEGORY)
    paper.highlights = result.get("highlights", [])
    paper.rating = float(result.get("rating", 5.0))
    paper.one_sentence = result.get("one_sentence", "")
    paper.applicable_scenarios = result.get("applicable_scenarios", "")
    return paper


def _fallback_process(papers: List[Paper]) -> List[Paper]:
    return [_fallback_single(p) for p in papers]


def _fallback_single(paper: Paper) -> Paper:
    """降级方案：关键词匹配分类 + 摘要截取"""
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
