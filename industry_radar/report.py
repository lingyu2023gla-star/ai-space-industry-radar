from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from .models import IndustryItem
from .storage import PROJECT_ROOT
from .text_utils import clean_text


DEFAULT_REPORT_PATH = PROJECT_ROOT / "outputs" / "weekly_report.md"


def generate_markdown(items: list[IndustryItem], top: int | None = None) -> str:
    sorted_items = sort_report_items(items)
    if top is not None:
        sorted_items = sorted_items[:top]

    lines = [
        "# AI & Commercial Space Weekly Brief",
        "",
        f"生成时间：{datetime.now().replace(microsecond=0).isoformat(sep=' ')}",
        "",
        "## 概览",
        "",
        f"- 记录数量：{len(sorted_items)}",
    ]

    if sorted_items:
        dates = [item.date for item in sorted_items if item.date]
        if dates:
            lines.append(f"- 日期范围：{min(dates)} 至 {max(dates)}")
    lines.append("")

    lines.extend(["## 行业分布", ""])
    if sorted_items:
        for industry, count in Counter(item.industry for item in sorted_items).most_common():
            lines.append(f"- {industry}：{count}")
    else:
        lines.append("- 暂无记录")
    lines.append("")

    lines.extend(["## 标签分布", ""])
    tag_counts = tag_distribution(sorted_items)
    if tag_counts:
        for tag, count in tag_counts:
            lines.append(f"- {tag}：{count}")
    else:
        lines.append("- 暂无标签")
    lines.append("")

    if not sorted_items:
        lines.extend(["## 重点条目", "", "暂无记录。", ""])
        return "\n".join(lines)

    lines.extend(["## 重点条目", ""])
    for index, item in enumerate(sorted_items, start=1):
        lines.extend(format_report_item(item, index))

    return "\n".join(lines)


def sort_report_items(items: list[IndustryItem]) -> list[IndustryItem]:
    return sorted(
        items,
        key=lambda item: (
            item.importance,
            item.date,
            item.created_at,
        ),
        reverse=True,
    )


def tag_distribution(items: list[IndustryItem]) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for item in items:
        for tag in item.tags.split(";"):
            cleaned = tag.strip()
            if cleaned:
                counter[cleaned] += 1
    return counter.most_common(10)


def format_report_item(item: IndustryItem, index: int) -> list[str]:
    lines = [f"#### {index}. {item.title}", ""]
    fields = [
        ("日期", item.date),
        ("行业", item.industry),
        ("类别", item.category),
        ("公司", item.company),
        ("重要性", f"{item.importance}/5" if item.importance else ""),
        ("标签", item.tags),
        ("来源", item.source),
        ("来源链接", item.source_url),
        ("摘要", clean_text(item.summary)),
        ("行业信号", item.signal),
    ]
    for label, value in fields:
        if value:
            lines.append(f"- {label}：{value}")
    lines.append("")
    return lines


def write_report(
    items: list[IndustryItem],
    path: Path = DEFAULT_REPORT_PATH,
    top: int | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_markdown(items, top=top), encoding="utf-8")
    return path
