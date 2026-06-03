from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .models import (
    IndustryItem,
    clean_prompt_value,
    normalize_importance,
    normalize_industry,
    normalize_tags,
)
from .enricher import (
    build_enrichment_prompt,
    merge_enrichment,
    needs_enrichment,
    parse_enrichment_result,
)
from .data_governance import build_dataset_stats, dedupe_items
from .dashboard import build_dashboard_data, render_dashboard_html, write_dashboard_html
from .config import (
    PIPELINE_DEFAULTS,
    load_json_config,
    merge_pipeline_config,
    validate_pipeline_config,
)
from .importer import import_items
from .fetcher import fetch_and_import
from .llm_client import call_deepseek_chat
from .pipeline import run_pipeline
from .report import DEFAULT_REPORT_PATH, write_report
from .run_logger import list_run_logs, read_run_log
from .source_health import (
    add_config_sources_to_health,
    build_source_health_report,
    collect_source_health,
    load_run_logs_for_health,
    load_source_names_from_config,
)
from .storage import append_item, filter_items, read_items, sort_by_date_desc, write_items


def prompt_required(label: str) -> str:
    while True:
        value = clean_prompt_value(input(f"{label}: "))
        if value:
            return value
        print(f"{label} 不能为空。")


def prompt_optional(label: str) -> str:
    return clean_prompt_value(input(f"{label}: "))


def prompt_industry() -> str:
    while True:
        value = clean_prompt_value(input("Industry [AI/Commercial Space]: "))
        if not value:
            print("Industry 不能为空。")
            continue
        try:
            return normalize_industry(value)
        except ValueError:
            print("Industry 仅支持 AI 或 Commercial Space。")


def prompt_importance() -> int:
    while True:
        try:
            return normalize_importance(input("Importance [1-5]: "))
        except ValueError:
            print("Importance 必须是 1 到 5 的整数。")


def add_command(_args: argparse.Namespace) -> int:
    item = IndustryItem.create(
        industry=prompt_industry(),
        category=prompt_required("Category"),
        company=prompt_required("Company"),
        title=prompt_required("Title"),
        source=prompt_required("Source"),
        source_url=prompt_optional("Source URL"),
        summary=prompt_required("Summary"),
        signal=prompt_required("Signal"),
        tags=normalize_tags(input("Tags [separated by ;]: ")),
        importance=prompt_importance(),
    )
    append_item(item)
    print(f"已添加：{item.id}")
    return 0


def list_command(args: argparse.Namespace) -> int:
    items = read_items()
    try:
        items = filter_items(
            items,
            industry=args.industry,
            category=args.category,
            tag=args.tag,
            company=args.company,
            since=args.since,
            until=args.until,
        )
    except ValueError as exc:
        print(f"筛选参数错误：{exc}")
        return 1
    items = sort_by_date_desc(items)[: args.limit]

    if not items:
        print("暂无记录。")
        return 0

    for item in items:
        line = (
            f"{item.date} | {item.industry} | {item.category} | "
            f"{item.company} | [{item.importance}/5] {item.title}"
        )
        if item.tags:
            line = f"{line} | tags: {item.tags}"
        print(line)
    return 0


def report_command(args: argparse.Namespace) -> int:
    if args.top is not None and args.top <= 0:
        print("报告参数错误：--top 必须是正整数。")
        return 1
    items = read_items()
    try:
        items = filter_items(
            items,
            industry=args.industry,
            since=args.since,
            until=args.until,
        )
    except ValueError as exc:
        print(f"筛选参数错误：{exc}")
        return 1
    path = write_report(items, Path(args.output), top=args.top)
    print(f"周报已生成：{path}")
    return 0


def import_command(args: argparse.Namespace) -> int:
    try:
        result = import_items(Path(args.file))
    except (OSError, ValueError) as exc:
        print(f"导入参数错误：{exc}")
        return 1

    print(f"Imported: {result.imported}")
    print(f"Skipped duplicates: {result.skipped_duplicates}")
    print(f"Failed: {result.failed}")
    for error in result.errors:
        print(error)
    return 0


def fetch_command(args: argparse.Namespace) -> int:
    try:
        result = fetch_and_import(
            Path(args.sources),
            limit=args.limit,
            industry=args.industry,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError) as exc:
        print(f"抓取参数错误：{exc}")
        return 1

    if args.dry_run:
        for record in result.records:
            print(
                f"[DRY RUN] {record['date']} | {record['industry']} | "
                f"{record['source']} | {record['title']}"
            )
        for error in result.errors:
            print(error)
        return 0

    print(f"Fetched: {result.fetched}")
    print(f"Imported: {result.imported}")
    print(f"Skipped duplicates: {result.skipped_duplicates}")
    print(f"Failed: {result.failed}")
    for error in result.errors:
        print(error)
    return 0


def enrich_command(args: argparse.Namespace) -> int:
    if args.limit <= 0:
        print("增强参数错误：--limit 必须是正整数。")
        return 1

    all_items = read_items()
    try:
        selected = filter_items(
            all_items,
            industry=args.industry,
            tag=args.tag,
            company=args.company,
            since=args.since,
            until=args.until,
        )
    except ValueError as exc:
        print(f"筛选参数错误：{exc}")
        return 1
    selected = selected[: args.limit]

    dry_run = args.dry_run or not args.apply
    enriched_by_id: dict[str, IndustryItem] = {}
    enriched = 0
    skipped = 0
    failed = 0

    for item in selected:
        if not needs_enrichment(item, overwrite=args.overwrite):
            skipped += 1
            continue
        try:
            content = call_deepseek_chat(
                build_enrichment_prompt(item),
                model=args.model,
            )
            enrichment = parse_enrichment_result(content)
            merged = merge_enrichment(item, enrichment, overwrite=args.overwrite)
        except ValueError as exc:
            failed += 1
            print(f"Failed: {item.title}: {exc}")
            continue

        enriched += 1
        enriched_by_id[item.id] = merged
        if dry_run:
            print(f"[DRY RUN] {item.title}")
            print(f"summary: {enrichment['summary']}")
            print(f"signal: {enrichment['signal']}")
            print(f"tags: {enrichment['tags']}")
            print(f"importance: {enrichment['importance']}")

    if args.apply and not dry_run:
        updated_items = [enriched_by_id.get(item.id, item) for item in all_items]
        write_items(updated_items)

    print(f"Selected: {len(selected)}")
    print(f"Enriched: {enriched}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")
    return 0


def stats_command(_args: argparse.Namespace) -> int:
    stats = build_dataset_stats(read_items())
    print(f"Total items: {stats['total']}")
    print("")
    print_counter("Industry distribution", stats["industry"])
    print_counter("Top categories", stats["category"], limit=10)
    print_counter("Top tags", stats["tags"], limit=10)
    print_counter("Top companies", stats["company"], limit=10)
    start_date, end_date = stats["date_range"]
    print("Date range:")
    print(f"{start_date} to {end_date}" if start_date and end_date else "N/A")
    print("")
    print_counter("Importance distribution", stats["importance"])
    return 0


def print_counter(title: str, counter, limit: int | None = None) -> None:
    print(f"{title}:")
    entries = counter.most_common(limit)
    if entries:
        for key, count in entries:
            print(f"- {key}: {count}")
    else:
        print("- N/A")
    print("")


def dedupe_command(args: argparse.Namespace) -> int:
    items = read_items()
    result = dedupe_items(items)
    should_apply = args.apply and not args.dry_run
    if not should_apply:
        for index, group in enumerate(result.groups, start=1):
            print(f"Duplicate group {index}:")
            for item in group:
                print(
                    f"- {item.date} | {item.industry} | {item.company} | "
                    f"{item.title} | {item.source_url}"
                )
            print("")
    else:
        write_items(result.items)

    print(f"Duplicate groups: {result.duplicate_groups}")
    print(f"Removed duplicates: {result.removed_duplicates}")
    print(f"Remaining items: {result.remaining_items}")
    return 0


def pipeline_command(args: argparse.Namespace) -> int:
    apply_changes = args.apply and not args.dry_run
    try:
        file_config = validate_pipeline_config(load_json_config(args.config))
        cli_overrides = validate_pipeline_config(
            {
                "sources": args.sources,
                "limit": args.limit,
                "industry": args.industry,
                "since": args.since,
                "until": args.until,
                "report": args.report,
                "top": args.top,
                "enrich": True if args.enrich else None,
                "overwrite": True if args.overwrite else None,
                "model": args.model,
                "skip_unhealthy_sources": True if args.skip_unhealthy_sources else None,
                "failure_rate_threshold": args.failure_rate_threshold,
                "min_source_runs": args.min_source_runs,
                "runs_dir": args.runs_dir,
            }
        )
        pipeline_config = merge_pipeline_config(
            PIPELINE_DEFAULTS,
            file_config,
            cli_overrides,
        )
        result = run_pipeline(
            sources_path=Path(pipeline_config["sources"]) if pipeline_config["sources"] else None,
            limit=pipeline_config["limit"],
            industry=pipeline_config["industry"],
            since=pipeline_config["since"],
            until=pipeline_config["until"],
            report_path=Path(pipeline_config["report"]),
            top=pipeline_config["top"],
            enrich=pipeline_config["enrich"],
            overwrite=pipeline_config["overwrite"],
            apply=apply_changes,
            model=pipeline_config["model"],
            save_run_log=args.save_run_log,
            runs_dir=pipeline_config["runs_dir"],
            skip_unhealthy_sources=pipeline_config["skip_unhealthy_sources"],
            failure_rate_threshold=pipeline_config["failure_rate_threshold"],
            min_source_runs=pipeline_config["min_source_runs"],
        )
    except (OSError, ValueError) as exc:
        print(f"Pipeline error: {exc}")
        return 1

    print(f"[Pipeline] Mode: {result.mode}")
    print("[Pipeline] Config:")
    print_pipeline_config(pipeline_config)
    if pipeline_config["skip_unhealthy_sources"]:
        print("[Pipeline] Source health policy:")
        print(f"- threshold: {pipeline_config['failure_rate_threshold'] * 100:.1f}%")
        print(f"- min_runs: {pipeline_config['min_source_runs']}")
        print(f"- skipped sources: {len(getattr(result, 'skipped_sources', []))}")
        for skipped in getattr(result, "skipped_sources", []):
            print("[Pipeline] Skipped unhealthy source:")
            print(f"- {skipped['name']}: {skipped['reason']}")
    if result.fetch_result is not None:
        print("[Pipeline] Step 1: fetch")
        print(f"Fetched: {result.fetch_result.fetched}")
        print(f"Imported: {result.fetch_result.imported}")
        print(f"Skipped duplicates: {result.fetch_result.skipped_duplicates}")
        print(f"Failed: {result.fetch_result.failed}")
        for error in result.fetch_result.errors:
            print(error)
    else:
        print("[Pipeline] Step 1: fetch skipped")

    print("[Pipeline] Step 2: dedupe")
    if result.dedupe_result is not None:
        print(f"Duplicate groups: {result.dedupe_result.duplicate_groups}")
        print(f"Removed duplicates: {result.dedupe_result.removed_duplicates}")
        print(f"Remaining items: {result.dedupe_result.remaining_items}")

    if pipeline_config["enrich"]:
        print("[Pipeline] Step 3: enrich")
        if result.enrich_result is not None:
            print(f"Selected: {result.enrich_result.selected}")
            print(f"Enriched: {result.enrich_result.enriched}")
            print(f"Skipped: {result.enrich_result.skipped}")
            print(f"Failed: {result.enrich_result.failed}")
            for error in result.enrich_result.errors:
                print(error)

    report_step = 4 if pipeline_config["enrich"] else 3
    print(f"[Pipeline] Step {report_step}: report")
    if result.report_written:
        print(f"周报已生成：{result.report_path}")
    else:
        print(f"Report would be generated: {result.report_path}")
    run_log_path = getattr(result, "run_log_path", None)
    if isinstance(run_log_path, str) and run_log_path:
        print(f"Run log saved: {run_log_path}")
    return 0


def runs_command(args: argparse.Namespace) -> int:
    if args.limit <= 0:
        print("runs 参数错误：--limit 必须是正整数。")
        return 1
    runs = list_run_logs(args.runs_dir, limit=args.limit)
    print("Recent runs:")
    for run in runs:
        duration = run.get("duration_seconds")
        duration_text = f"{duration:.2f}s" if isinstance(duration, (int, float)) else "N/A"
        print(
            f"{run['run_id']} | {run['command']} | {run['mode']} | "
            f"{run['status']} | errors: {run['total_errors']} | {duration_text}"
        )
    return 0


def run_show_command(args: argparse.Namespace) -> int:
    try:
        run_log = read_run_log(args.run_id_or_path, runs_dir=args.runs_dir)
    except OSError as exc:
        print(f"Run log error: {exc}")
        return 1

    print(f"run_id: {run_log.get('run_id', '')}")
    print(f"command: {run_log.get('command', '')}")
    print(f"mode: {run_log.get('mode', '')}")
    print(f"started_at: {run_log.get('started_at', '')}")
    print(f"ended_at: {run_log.get('ended_at', '')}")
    print(f"duration: {run_log.get('duration_seconds', '')}")
    summary = run_log.get("summary", {})
    print(f"summary status: {summary.get('status', '')}")
    print(f"total_errors: {summary.get('total_errors', 0)}")
    print("steps:")
    for step in run_log.get("steps", []):
        print(f"- {step.get('name', '')} | {step.get('status', '')}")
        print(f"  metrics: {step.get('metrics', {})}")
        errors = step.get("errors", [])
        if errors:
            print(f"  errors: {errors}")
    return 0


def source_health_command(args: argparse.Namespace) -> int:
    if args.limit <= 0:
        print("source-health 参数错误：--limit 必须是正整数。")
        return 1
    run_logs = load_run_logs_for_health(args.runs_dir, limit=args.limit)
    health = collect_source_health(run_logs)
    source_names = load_source_names_from_config(args.sources)
    if source_names:
        health = add_config_sources_to_health(health, source_names, len(run_logs))
    print(build_source_health_report(health))
    return 0


def dashboard_command(args: argparse.Namespace) -> int:
    if args.top <= 0:
        print("dashboard 参数错误：--top 必须是正整数。")
        return 1
    items = read_items()
    run_summaries = list_run_logs(args.runs_dir, limit=args.top)
    run_logs = load_run_logs_for_health(args.runs_dir, limit=args.top)
    health = collect_source_health(run_logs)
    source_names = load_source_names_from_config(args.sources)
    if source_names:
        health = add_config_sources_to_health(health, source_names, len(run_logs))
    data = build_dashboard_data(
        items,
        run_summaries=run_summaries,
        source_health=health,
        top_n=args.top,
    )
    html_text = render_dashboard_html(data, title=args.title)
    output_path = write_dashboard_html(html_text, args.output)
    print(f"Dashboard generated: {output_path}")
    return 0


def print_pipeline_config(config: dict) -> None:
    for key in (
        "sources",
        "limit",
        "industry",
        "top",
        "report",
        "enrich",
        "overwrite",
        "skip_unhealthy_sources",
        "failure_rate_threshold",
        "min_source_runs",
        "runs_dir",
    ):
        print(f"- {key}: {format_config_value(config.get(key))}")


def format_config_value(value) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="industry_radar",
        description="AI 与商业航天行业调研雷达 MVP",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"industry-radar {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="交互式添加一条行业信息")
    add_parser.set_defaults(func=add_command)

    list_parser = subparsers.add_parser("list", help="展示行业信息")
    list_parser.add_argument("--industry", help="按行业筛选")
    list_parser.add_argument("--category", help="按分类筛选")
    list_parser.add_argument("--tag", help="按标签筛选")
    list_parser.add_argument("--company", help="按公司/机构筛选，支持包含匹配")
    list_parser.add_argument("--since", help="只展示 date >= since 的记录，格式 YYYY-MM-DD")
    list_parser.add_argument("--until", help="只展示 date <= until 的记录，格式 YYYY-MM-DD")
    list_parser.add_argument("--limit", type=int, default=10, help="展示条数，默认 10")
    list_parser.set_defaults(func=list_command)

    report_parser = subparsers.add_parser("report", help="生成 Markdown 周报")
    report_parser.add_argument("--industry", help="按行业筛选")
    report_parser.add_argument("--since", help="只纳入 date >= since 的记录，格式 YYYY-MM-DD")
    report_parser.add_argument("--until", help="只纳入 date <= until 的记录，格式 YYYY-MM-DD")
    report_parser.add_argument("--top", type=int, help="只输出排序后的前 N 条")
    report_parser.add_argument(
        "--output",
        default=str(DEFAULT_REPORT_PATH),
        help="输出文件路径，默认 outputs/weekly_report.md",
    )
    report_parser.set_defaults(func=report_command)

    import_parser = subparsers.add_parser("import", help="批量导入行业信息")
    import_parser.add_argument("--file", required=True, help="JSON 或 CSV 导入文件路径")
    import_parser.set_defaults(func=import_command)

    fetch_parser = subparsers.add_parser("fetch", help="从 RSS / Atom 源抓取行业信息")
    fetch_parser.add_argument("--sources", required=True, help="sources JSON 配置文件路径")
    fetch_parser.add_argument("--dry-run", action="store_true", help="只打印候选记录，不写入 CSV")
    fetch_parser.add_argument("--limit", type=int, default=10, help="每个 source 最多读取条数，默认 10")
    fetch_parser.add_argument("--industry", help="只抓取指定行业的 source")
    fetch_parser.set_defaults(func=fetch_command)

    enrich_parser = subparsers.add_parser("enrich", help="使用 DeepSeek 增强行业信息")
    enrich_parser.add_argument("--limit", type=int, default=5, help="处理条数，默认 5")
    enrich_parser.add_argument("--industry", help="按行业筛选")
    enrich_parser.add_argument("--tag", help="按标签筛选")
    enrich_parser.add_argument("--company", help="按公司/机构筛选，支持包含匹配")
    enrich_parser.add_argument("--since", help="只增强 date >= since 的记录，格式 YYYY-MM-DD")
    enrich_parser.add_argument("--until", help="只增强 date <= until 的记录，格式 YYYY-MM-DD")
    enrich_parser.add_argument("--dry-run", action="store_true", help="只打印增强结果，不写回 CSV")
    enrich_parser.add_argument("--apply", action="store_true", help="写回 CSV")
    enrich_parser.add_argument("--overwrite", action="store_true", help="覆盖已有增强字段")
    enrich_parser.add_argument("--model", help="覆盖默认 DeepSeek 模型")
    enrich_parser.set_defaults(func=enrich_command)

    stats_parser = subparsers.add_parser("stats", help="查看数据集统计")
    stats_parser.set_defaults(func=stats_command)

    dedupe_parser = subparsers.add_parser("dedupe", help="清理已有 CSV 中的重复记录")
    dedupe_parser.add_argument("--dry-run", action="store_true", help="预览重复组，不写回 CSV")
    dedupe_parser.add_argument("--apply", action="store_true", help="执行合并去重并写回 CSV")
    dedupe_parser.set_defaults(func=dedupe_command)

    pipeline_parser = subparsers.add_parser("pipeline", help="执行 fetch/dedupe/enrich/report 工作流")
    pipeline_parser.add_argument("--config", help="Pipeline JSON 配置文件路径")
    pipeline_parser.add_argument("--sources", help="RSS sources 配置文件路径")
    pipeline_parser.add_argument("--limit", type=int, default=None, help="每个 source 抓取条数，默认 5")
    pipeline_parser.add_argument("--industry", help="按行业筛选")
    pipeline_parser.add_argument("--since", help="用于 enrich/report 的起始日期，格式 YYYY-MM-DD")
    pipeline_parser.add_argument("--until", help="用于 enrich/report 的截止日期，格式 YYYY-MM-DD")
    pipeline_parser.add_argument(
        "--report",
        default=None,
        help="报告输出路径，默认 outputs/pipeline_report.md",
    )
    pipeline_parser.add_argument("--top", type=int, help="报告输出前 N 条")
    pipeline_parser.add_argument("--enrich", action="store_true", help="执行 DeepSeek enrich")
    pipeline_parser.add_argument("--overwrite", action="store_true", help="传给 enrich，覆盖已有字段")
    pipeline_parser.add_argument("--model", help="传给 enrich 的 DeepSeek 模型")
    pipeline_parser.add_argument("--dry-run", action="store_true", help="dry-run，不写 CSV 或报告")
    pipeline_parser.add_argument("--apply", action="store_true", help="允许执行写操作")
    pipeline_parser.add_argument("--save-run-log", action="store_true", help="保存 pipeline 运行日志")
    pipeline_parser.add_argument("--runs-dir", default=None, help="运行日志目录，默认 runs")
    pipeline_parser.add_argument("--skip-unhealthy-sources", action="store_true", help="按历史失败率跳过不健康 source")
    pipeline_parser.add_argument("--failure-rate-threshold", type=float, default=None, help="source 跳过失败率阈值，默认 0.8")
    pipeline_parser.add_argument("--min-source-runs", type=int, default=None, help="启用跳过判断所需最小历史次数，默认 3")
    pipeline_parser.set_defaults(func=pipeline_command)

    runs_parser = subparsers.add_parser("runs", help="查看最近 pipeline 运行日志")
    runs_parser.add_argument("--limit", type=int, default=10, help="展示条数，默认 10")
    runs_parser.add_argument("--runs-dir", default="runs", help="运行日志目录，默认 runs")
    runs_parser.set_defaults(func=runs_command)

    run_show_parser = subparsers.add_parser("run-show", help="查看某次运行日志详情")
    run_show_parser.add_argument("run_id_or_path", help="run_id 或 run log 文件路径")
    run_show_parser.add_argument("--runs-dir", default="runs", help="运行日志目录，默认 runs")
    run_show_parser.set_defaults(func=run_show_command)

    source_health_parser = subparsers.add_parser("source-health", help="分析数据源健康状态")
    source_health_parser.add_argument("--runs-dir", default="runs", help="运行日志目录，默认 runs")
    source_health_parser.add_argument("--limit", type=int, default=20, help="分析最近 N 条 run log，默认 20")
    source_health_parser.add_argument("--sources", help="sources JSON 配置文件路径")
    source_health_parser.set_defaults(func=source_health_command)

    dashboard_parser = subparsers.add_parser("dashboard", help="导出静态 HTML Dashboard")
    dashboard_parser.add_argument("--output", default="outputs/dashboard.html", help="输出 HTML 路径，默认 outputs/dashboard.html")
    dashboard_parser.add_argument("--top", type=int, default=10, help="展示前 N 条，默认 10")
    dashboard_parser.add_argument("--runs-dir", default="runs", help="运行日志目录，默认 runs")
    dashboard_parser.add_argument("--sources", help="sources JSON 配置文件路径")
    dashboard_parser.add_argument("--title", default="AI Space Industry Radar Dashboard", help="Dashboard 标题")
    dashboard_parser.set_defaults(func=dashboard_command)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
