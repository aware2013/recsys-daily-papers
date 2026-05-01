#!/usr/bin/env python3
"""推荐算法论文日报 — 编排入口"""

import argparse
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import DailyDigest
from src.config import get_bucket, PAPERS_PER_BUCKET
from src.fetcher.arxiv_fetcher import fetch_papers
from src.fetcher.semantic_scholar import enrich_papers
from src.processor.filter import filter_papers, save_processed_ids
from src.processor.llm_processor import process_papers as llm_process
from src.processor.ranker import rank_papers
from src.output.markdown_generator import generate_daily_report, update_index
from src.output.feishu_notifier import send_notification
from src.output.feishu_bitable import sync_to_bitable

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
    logger.info("[1/7] Fetching papers from arXiv...")
    papers = fetch_papers()
    total_candidates = len(papers)
    if not papers:
        logger.info("No new papers found today")
        return {"status": "empty", "date": date_str}

    # Step 2: Filter
    logger.info("[2/7] Filtering & deduplicating...")
    papers = filter_papers(papers, PROCESSED_IDS_FILE)
    after_filter = len(papers)

    # Step 3: Enrich
    logger.info("[3/7] Enriching with Semantic Scholar...")
    papers = enrich_papers(papers)

    # Step 4: LLM Process
    logger.info("[4/7] LLM summarization & classification...")
    papers = llm_process(papers)

    # Step 5: Split into buckets
    logger.info("[5/7] Splitting papers into buckets...")
    bucket_map = {}
    for p in papers:
        bucket_map[p.arxiv_id] = get_bucket(p.category)

    recsys_papers = [p for p in papers if bucket_map[p.arxiv_id] == "推荐算法"]
    growth_papers = [p for p in papers if bucket_map[p.arxiv_id] == "营销增长"]

    # Step 6: Rank each bucket separately
    logger.info("[6/7] Ranking each bucket...")
    recsys_papers = rank_papers(recsys_papers)[:PAPERS_PER_BUCKET]
    growth_papers = rank_papers(growth_papers)[:PAPERS_PER_BUCKET]

    all_papers = recsys_papers + growth_papers

    # Step 7: Generate outputs
    logger.info("[7/7] Generating outputs...")
    digest = DailyDigest(
        date=date_str,
        total_candidates=total_candidates,
        after_filter=after_filter,
        after_dedup=len(all_papers),
        papers=all_papers,
        bucket_map=bucket_map,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    digest.stats = {"推荐算法": len(recsys_papers), "营销增长": len(growth_papers)}

    year_month = date_str[:7].replace("-", "/")
    report_path = os.path.join(PAPERS_DIR, year_month, f"{date_str[-2:]}.md")
    generate_daily_report(digest, report_path)
    update_index(digest, INDEX_PATH)

    ids = [p.arxiv_id for p in all_papers]
    save_processed_ids(PROCESSED_IDS_FILE, ids)

    if not dry_run:
        send_notification(digest)
        sync_to_bitable(all_papers, bucket_map, date_str)
    else:
        logger.info("[DRY RUN] Skipping Feishu push and Bitable sync")

    logger.info(f"=== Digest complete: 推荐算法 {len(recsys_papers)} + 营销增长 {len(growth_papers)} = {len(all_papers)} papers ===")
    return {"status": "ok", "date": date_str, "推荐算法": len(recsys_papers), "营销增长": len(growth_papers)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="推荐算法论文日报生成器")
    parser.add_argument("--date", default="", help="日期 (YYYY-MM-DD), 默认今天")
    parser.add_argument("--dry-run", action="store_true", help="试运行模式，不推送飞书")
    args = parser.parse_args()

    result = run(date_str=args.date, dry_run=args.dry_run)
    logger.info(f"Result: {result}")
