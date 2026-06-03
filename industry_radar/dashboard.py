from __future__ import annotations

import html
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def build_dashboard_data(
    items: list[Any],
    run_summaries: list[dict] | None = None,
    source_health: dict | None = None,
    top_n: int = 10,
) -> dict:
    if top_n <= 0:
        raise ValueError("top_n must be a positive integer")
    dates = [item_value(item, "date") for item in items if item_value(item, "date")]
    return {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "total_items": len(items),
        "industry_distribution": dict(
            Counter(item_value(item, "industry") for item in items if item_value(item, "industry"))
        ),
        "category_distribution": dict(
            Counter(item_value(item, "category") for item in items if item_value(item, "category"))
        ),
        "tag_distribution": dict(build_tag_counter(items)),
        "company_distribution": dict(
            Counter(item_value(item, "company") for item in items if item_value(item, "company"))
        ),
        "importance_distribution": dict(
            Counter(str(item_value(item, "importance")) for item in items if item_value(item, "importance") != "")
        ),
        "date_range": (min(dates), max(dates)) if dates else ("", ""),
        "recent_items": sort_recent_items(items)[:top_n],
        "recent_runs": (run_summaries or [])[:top_n],
        "source_health": sort_source_health(source_health or {}),
    }


def render_dashboard_html(
    data: dict,
    title: str = "AI Space Industry Radar Dashboard",
) -> str:
    escaped_title = escape(title)
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>{escaped_title}</title>",
            f"  <style>{dashboard_css()}</style>",
            "</head>",
            "<body>",
            f"  <h1>{escaped_title}</h1>",
            f"  <p class=\"muted\">Generated at: {escape(data.get('generated_at', ''))}</p>",
            render_overview(data),
            render_counter_section("Industry Distribution", data.get("industry_distribution", {})),
            render_counter_section("Top Tags", data.get("tag_distribution", {})),
            render_counter_section("Top Companies", data.get("company_distribution", {})),
            render_counter_section("Importance Distribution", data.get("importance_distribution", {})),
            render_recent_items(data.get("recent_items", [])),
            render_recent_runs(data.get("recent_runs", [])),
            render_source_health(data.get("source_health", [])),
            "</body>",
            "</html>",
        ]
    )


def write_dashboard_html(html_text: str, output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")
    return str(path)


def item_value(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        return item.get(field, "")
    return getattr(item, field, "")


def build_tag_counter(items: list[Any]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for item in items:
        for tag in str(item_value(item, "tags")).split(";"):
            cleaned = tag.strip()
            if cleaned:
                counter[cleaned] += 1
    return counter


def sort_recent_items(items: list[Any]) -> list[dict]:
    rows = [
        {
            "date": item_value(item, "date"),
            "industry": item_value(item, "industry"),
            "company": item_value(item, "company"),
            "title": item_value(item, "title"),
            "importance": item_value(item, "importance"),
            "tags": item_value(item, "tags"),
        }
        for item in items
    ]
    return sorted(
        rows,
        key=lambda item: (str(item.get("date", "")), int_or_zero(item.get("importance"))),
        reverse=True,
    )


def sort_source_health(source_health: dict) -> list[dict]:
    return sorted(
        source_health.values(),
        key=lambda item: (-float(item.get("failure_rate", 0.0)), str(item.get("source", ""))),
    )


def int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def render_overview(data: dict) -> str:
    start_date, end_date = data.get("date_range", ("", ""))
    cards = [
        ("Total Items", data.get("total_items", 0)),
        ("Date Range", f"{start_date} to {end_date}" if start_date and end_date else "N/A"),
        ("Recent Runs", len(data.get("recent_runs", []))),
        ("Sources", len(data.get("source_health", []))),
    ]
    content = "".join(
        f'<div class="card"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div></div>'
        for label, value in cards
    )
    return f"  <section><h2>Overview</h2><div class=\"cards\">{content}</div></section>"


def render_counter_section(title: str, counter: dict) -> str:
    rows = sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))
    return render_table(title, ["Name", "Count"], rows)


def render_recent_items(items: list[dict]) -> str:
    rows = [
        [
            item.get("date", ""),
            item.get("industry", ""),
            item.get("company", ""),
            item.get("title", ""),
            item.get("importance", ""),
            item.get("tags", ""),
        ]
        for item in items
    ]
    return render_table(
        "Recent Items",
        ["date", "industry", "company", "title", "importance", "tags"],
        rows,
    )


def render_recent_runs(runs: list[dict]) -> str:
    rows = [
        [
            run.get("run_id", ""),
            run.get("mode", ""),
            run.get("status", ""),
            run.get("total_errors", 0),
            run.get("duration_seconds", ""),
        ]
        for run in runs
    ]
    return render_table(
        "Recent Runs",
        ["run_id", "mode", "status", "total_errors", "duration_seconds"],
        rows,
    )


def render_source_health(health_rows: list[dict]) -> str:
    rows = [
        [
            row.get("source", ""),
            row.get("runs_seen", 0),
            row.get("failures", 0),
            f"{float(row.get('failure_rate', 0.0)) * 100:.1f}%",
            row.get("last_status", ""),
            row.get("last_error", ""),
        ]
        for row in health_rows
    ]
    return render_table(
        "Source Health",
        ["source", "runs_seen", "failures", "failure_rate", "last_status", "last_error"],
        rows,
    )


def render_table(title: str, headers: list[str], rows: list) -> str:
    header_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    if rows:
        body_html = "".join(
            "<tr>"
            + "".join(f"<td>{escape(cell)}</td>" for cell in row)
            + "</tr>"
            for row in rows
        )
    else:
        body_html = f'<tr><td colspan="{len(headers)}" class="muted">No data</td></tr>'
    return (
        f"  <section><h2>{escape(title)}</h2>"
        f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"
        "</section>"
    )


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def dashboard_css() -> str:
    return """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #17202a; background: #f7f8fa; }
h1 { margin-bottom: 4px; }
section { margin: 24px 0; }
.muted { color: #667085; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.card { background: #fff; border: 1px solid #e4e7ec; border-radius: 8px; padding: 16px; }
.label { color: #667085; font-size: 13px; }
.value { font-size: 20px; font-weight: 650; margin-top: 6px; }
table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e4e7ec; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #eef0f3; vertical-align: top; }
th { background: #f0f2f5; font-size: 13px; }
tr:last-child td { border-bottom: none; }
""".strip()
