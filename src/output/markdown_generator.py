"""Jinja2 模板渲染日报 Markdown 和首页索引"""

import json
import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.models import DailyDigest

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


def generate_daily_report(digest: DailyDigest, output_path: str) -> str:
    """生成每日论文日报 Markdown"""
    env = _create_env()
    template = env.get_template("daily_report.md.j2")

    # 按分类分组
    category_groups: dict[str, list] = {}
    for paper in digest.papers:
        cat = paper.category or "其他"
        category_groups.setdefault(cat, []).append(paper)

    top3 = digest.papers[:3]
    stars = lambda r: "⭐" * int(r / 2) if r else "—"

    content = template.render(
        date=digest.date,
        total_candidates=digest.total_candidates,
        after_filter=digest.after_filter,
        after_dedup=digest.after_dedup,
        top3=top3,
        papers=digest.papers,
        category_groups=category_groups,
        generated_at=digest.generated_at or datetime.now().strftime("%Y-%m-%d %H:%M"),
        stars=stars,
        enumerate=enumerate,
    )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    logger.info(f"Daily report saved: {output_path}")
    return content


def update_index(digest: DailyDigest, output_path: str) -> None:
    """更新首页索引，追加最新日报链接"""
    env = _create_env()
    template = env.get_template("index.md.j2")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 收集所有已有日报
    existing = _gather_links(path.parent)
    today_link = {
        "date": digest.date,
        "count": len(digest.papers),
        "categories": str(len({p.category for p in digest.papers})),
    }

    content = template.render(
        latest=today_link,
        recent=existing[:30],
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    path.write_text(content, encoding="utf-8")
    logger.info(f"Index updated: {output_path}")


def _create_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(),
    )


def _gather_links(papers_root: Path) -> list[dict]:
    links = []
    if not papers_root.exists():
        return links
    for year_dir in sorted(papers_root.iterdir(), reverse=True):
        if not year_dir.is_dir():
            continue
        for month_dir in sorted(year_dir.iterdir(), reverse=True):
            if not month_dir.is_dir():
                continue
            for file in sorted(month_dir.glob("*.md"), reverse=True):
                rel = file.relative_to(papers_root)
                date_str = f"{year_dir.name}-{month_dir.name}-{file.stem}"
                links.append({"date": date_str, "path": str(rel)})
    return links
