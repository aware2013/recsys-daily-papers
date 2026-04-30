#!/usr/bin/env python3
"""推荐算法论文日报 — 编排入口"""

import argparse
import logging
import os
import sys
from datetime import datetime

# 确保项目根在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import DailyDigest
from src.fetcher.arxiv_fetcher import fetch_papers
from src.fetcher.semantic_scholar import enrich_papers
from src.processor.filter import filter_papers, save_processed_ids
from src.processor.llm_processor import process_papers as llm_process
from src.processor.ranker import rank_papers
from src.output.markdown_generator import generate_daily_report, update_index
from src.output.feishu_notifier import send_notification

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS_DIR = os.path.join(PROJECT_ROOT, "papers")
INDEX_PATH = os.path.join(PROJECT_ROOT, "docs", "index.md")
PROCESSED_IDS_FILE = os.path.join(PROJECT_ROOT, "data", "processed_ids.yaml")


def run(date_str: str = "", dry_run: bool = False):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"=== Starting daily digest for {date_str} ===")

    # Step 1: Fetch
    logger.info("[1/6] Fetching papers from arXiv...")
    papers = fetch_papers()
    total_candidates = len(papers)
    if not papers:
        logger.info("No new papers found today")
        return {"status": "empty", "date": date_str}

    # Step 2: Filter
    logger.info("[2/6] Filtering & deduplicating...")
    papers = filter_papers(papers, PROCESSED_IDS_FILE)
    after_filter = len(papers)

    # Step 3: Enrich
    logger.info("[3/6] Enriching with Semantic Scholar...")
    papers = enrich_papers(papers)

    # Step 4: LLM Process
    logger.info("[4/6] LLM summarization & classification...")
    papers = llm_process(papers)

    # Step 5: Rank
    logger.info("[5/6] Ranking papers...")
    papers = rank_papers(papers)

    # Step 6: Generate outputs
    logger.info("[6/6] Generating outputs...")
    digest = DailyDigest(
        date=date_str,
        total_candidates=total_candidates,
        after_filter=after_filter,
        after_dedup=len(papers),
        papers=papers,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    year_month = date_str[:7].replace("-", "/")
    report_path = os.path.join(PAPERS_DIR, year_month, f"{date_str[-2:]}.md")
    generate_daily_report(digest, report_path)
    update_index(digest, INDEX_PATH)

    # 记录已处理
    ids = [p.arxiv_id for p in papers]
    save_processed_ids(PROCESSED_IDS_FILE, ids)

    # 飞书推送
    if not dry_run:
        send_notification(digest)
    else:
        logger.info("[DRY RUN] Skipping Feishu push and git commit")

    logger.info(f"=== Digest complete: {len(papers)} papers ===")
    return {"status": "ok", "date": date_str, "count": len(papers)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="推荐算法论文日报生成器")
    parser.add_argument("--date", default="", help="日期 (YYYY-MM-DD), 默认今天")
    parser.add_argument("--dry-run", action="store_true", help="试运行模式，不推送飞书")
    args = parser.parse_args()

    result = run(date_str=args.date, dry_run=args.dry_run)
    logger.info(f"Result: {result}")
