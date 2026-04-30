"""Gemini LLM 处理器：中文摘要、分类、评分。失败时降级为关键词方案"""

import json
import logging
import os
import re
import time
from typing import List

from src.config import (
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    GEMINI_MAX_TOKENS,
    SYSTEM_PROMPT,
    PAPER_CATEGORIES,
    FALLBACK_CATEGORY,
)
from src.models import Paper

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 5.0  # 秒
CALL_DELAY = 2.0  # 每次调用间隔


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
        success_count = 0
        fail_count = 0

        for paper in papers:
            result = _call_with_retry(client, paper)
            if result:
                results.append(_apply_result(paper, result))
                success_count += 1
            else:
                results.append(_fallback_single(paper))
                fail_count += 1
            # 请求间延迟
            time.sleep(CALL_DELAY)

        logger.info(f"LLM processed: {success_count} succeeded, {fail_count} fallback")
        return results

    except ImportError:
        logger.warning("google-genai not installed, using keyword fallback")
        return _fallback_process(papers)
    except Exception as e:
        logger.error(f"Gemini API unreachable: {e}, using keyword fallback")
        return _fallback_process(papers)


def _call_with_retry(client, paper: Paper) -> dict | None:
    """带指数退避重试的 Gemini 调用"""
    for attempt in range(MAX_RETRIES):
        try:
            return _call_gemini(client, paper)
        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit = "429" in str(e) or "resource_exhausted" in error_msg

            if attempt < MAX_RETRIES - 1:
                wait = INITIAL_BACKOFF * (2 ** attempt) + (time.time() % 3)
                if is_rate_limit:
                    wait = max(wait, 10.0)  # 限流时至少等10秒
                logger.warning(
                    f"Gemini {paper.arxiv_id}: attempt {attempt + 1} failed "
                    f"({'rate limit' if is_rate_limit else 'error'}), "
                    f"retrying in {wait:.1f}s... ({e})"
                )
                time.sleep(wait)
            else:
                logger.error(f"Gemini {paper.arxiv_id}: all {MAX_RETRIES} attempts failed: {e}")
                return None

    return None


def _call_gemini(client, paper: Paper) -> dict:
    user_text = f"标题: {paper.title}\n摘要: {paper.abstract}"
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
