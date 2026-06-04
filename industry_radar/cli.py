from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import datetime
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
from .importer import import_records
from .fetcher import fetch_and_import
from .knowledge_base import (
    build_ask_prompt,
    build_citation_entries,
    build_documents_from_items,
    build_retrieval_answer,
    format_citations_text,
)
from .llm_client import call_deepseek_chat
from .pipeline import run_pipeline
from .report import DEFAULT_REPORT_PATH, write_report
from .report_ingestor import ingest_report_file
from .research_collection import (
    build_research_paths,
    create_research_metadata,
    delete_research_session,
    generate_research_id,
    list_research_sessions,
    mark_research_ingested,
    read_research_markdown,
    read_research_metadata,
    resolve_research_path,
    write_research_session,
)
from .research_exporter import (
    build_export_manifest,
    export_research_pack,
    select_research_sessions,
    summarize_export_result,
)
from .research_importer import import_research_pack, render_import_plan, summarize_import_result
from .research_index import (
    build_research_collection_stats,
    build_research_documents,
    build_research_search_report,
    render_research_stats,
    search_research_documents,
)
from .research_session import (
    build_research_context,
    build_research_llm_prompt,
    generate_local_research_notes,
    render_research_report,
    write_research_report,
)
from .retrievers import EmbeddingRetriever, KeywordRetriever, SQLiteFTSRetriever
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


def report_ingest_command(args: argparse.Namespace) -> int:
    if args.summary_only and args.details_only:
        print("report-ingest 参数错误：--summary-only 和 --details-only 不能同时使用。")
        return 1
    include_summary = not args.details_only
    include_details = not args.summary_only
    try:
        candidates = ingest_report_file(
            args.file,
            include_summary_item=include_summary,
            include_detail_items=include_details,
            default_industry=args.industry,
        )
    except (OSError, ValueError) as exc:
        print(f"Report ingest error: {exc}")
        return 1

    should_apply = args.apply and not args.dry_run
    if not should_apply:
        for candidate in candidates:
            label = "Report item" if candidate.get("category") == "Report" else "Detail item"
            print(f"[DRY RUN] {label}: {candidate.get('title', '')}")
        print(f"Candidates: {len(candidates)}")
        return 0

    result = import_records(candidates)
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
            ingest_report=args.ingest_report,
            ingest_report_summary_only=args.ingest_report_summary_only,
            ingest_report_details_only=args.ingest_report_details_only,
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
    if args.ingest_report:
        ingest_step = report_step + 1
        print(f"[Pipeline] Step {ingest_step}: ingest report")
        if result.report_ingest_result is None:
            print(f"Report ingest would run for: {result.report_path}")
        else:
            print(f"Candidates: {result.report_ingest_candidates}")
            print(f"Imported: {result.report_ingest_result.imported}")
            print(f"Skipped duplicates: {result.report_ingest_result.skipped_duplicates}")
            print(f"Failed: {result.report_ingest_result.failed}")
            for error in result.report_ingest_result.errors:
                print(error)
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


def ask_command(args: argparse.Namespace) -> int:
    if args.top <= 0:
        print("ask 参数错误：--top 必须是正整数。")
        return 1
    items = read_items()
    documents = build_documents_from_items(items)
    retrievers = {
        "keyword": KeywordRetriever,
        "embedding": EmbeddingRetriever,
        "fts": SQLiteFTSRetriever,
    }
    retriever = retrievers[args.retriever]()
    try:
        results = retriever.search(
            args.query,
            documents,
            top_k=args.top,
            industry=args.industry,
            tag=args.tag,
            company=args.company,
            since=args.since,
            until=args.until,
        )
    except ValueError as exc:
        print(f"ask 参数错误：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"ask 检索错误：{exc}")
        return 1

    if args.llm and results:
        try:
            answer = call_deepseek_chat(
                build_ask_prompt(args.query, results),
                model=args.model,
                response_format_json=False,
            )
        except ValueError as exc:
            print(f"LLM error: {exc}")
            return 1
        print(answer)
        if args.citations:
            citations_text = format_citations_text(build_citation_entries(results))
            if citations_text:
                print("")
                print("证据列表：")
                print(citations_text)
    else:
        print(
            build_retrieval_answer(
                args.query,
                results,
                with_citations=args.citations,
                include_sources=args.citations,
            )
        )

    if args.show_sources and results:
        print("")
        print("Sources:")
        for index, result in enumerate(results, start=1):
            print(
                f"{index}. [{result['score']:.1f}] {result.get('date', '')} | "
                f"{result.get('company', '')} | {result.get('title', '')}"
            )
            if result.get("source_url"):
                print(f"   {result['source_url']}")
    return 0


def research_command(args: argparse.Namespace) -> int:
    if args.top <= 0:
        print("research 参数错误：--top 必须是正整数。")
        return 1
    if args.ingest_summary_only and args.ingest_details_only:
        print("research 参数错误：--ingest-summary-only 和 --ingest-details-only 不能同时使用。")
        return 1
    items = read_items()
    documents = build_documents_from_items(items)
    retrievers = {
        "keyword": KeywordRetriever,
        "embedding": EmbeddingRetriever,
        "fts": SQLiteFTSRetriever,
    }
    retriever = retrievers[args.retriever]()
    try:
        results = retriever.search(
            args.query,
            documents,
            top_k=args.top,
            industry=args.industry,
            tag=args.tag,
            company=args.company,
            since=args.since,
            until=args.until,
        )
    except ValueError as exc:
        print(f"research 参数错误：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"research 检索错误：{exc}")
        return 1

    context = build_research_context(args.query, results)
    local_notes = generate_local_research_notes(context)
    llm_notes = None
    if args.llm and context["evidence_count"]:
        try:
            llm_notes = call_deepseek_chat(
                build_research_llm_prompt(context),
                model=args.model,
                response_format_json=False,
            )
        except ValueError as exc:
            print(f"LLM error: {exc}")
            return 1

    filters = {
        "industry": args.industry,
        "tag": args.tag,
        "company": args.company,
        "since": args.since,
        "until": args.until,
    }
    research_id = args.research_id or generate_research_id(args.query)
    session_paths = build_research_paths(research_id, args.research_dir)
    session_metadata = create_research_metadata(
        research_id,
        args.query,
        session_paths["markdown"],
        args.retriever,
        args.top,
        filters,
        context["evidence_count"],
        bool(args.llm),
    )
    markdown = render_research_report(
        args.query,
        local_notes,
        llm_notes=llm_notes,
        metadata={
            "generated_at": datetime.now().replace(microsecond=0).isoformat(),
            "research_id": research_id if args.save_session else "",
            "retriever": args.retriever,
            "top_k": args.top,
            "llm_enabled": bool(args.llm),
            "evidence_count": context["evidence_count"],
        },
    )

    should_apply = args.apply and not args.dry_run
    if should_apply:
        output_path = write_research_report(markdown, args.output)
        print(f"Research report generated: {output_path}")
    else:
        print(f"[DRY RUN] Research report would be generated: {args.output}")
        print(markdown)

    if args.save_session:
        if should_apply:
            paths = write_research_session(markdown, session_metadata, research_dir=args.research_dir)
            print(f"Research session saved: {paths['markdown']}")
            print(f"Metadata saved: {paths['metadata']}")
        else:
            print(f"Research session would be saved: {session_paths['markdown']}")

    if args.ingest:
        if not should_apply:
            print(f"Report ingest would run for: {args.output}")
            return 0
        ingest_path = session_paths["markdown"] if args.save_session else args.output
        result = import_records(
            ingest_report_file(
                ingest_path,
                include_summary_item=not args.ingest_details_only,
                include_detail_items=not args.ingest_summary_only,
            )
        )
        print("Report ingest:")
        print(f"Imported: {result.imported}")
        print(f"Skipped duplicates: {result.skipped_duplicates}")
        print(f"Failed: {result.failed}")
        for error in result.errors:
            print(error)
        if args.save_session and result.failed == 0:
            mark_research_ingested(research_id, research_dir=args.research_dir)
    return 0


def research_list_command(args: argparse.Namespace) -> int:
    if args.limit <= 0:
        print("research-list 参数错误：--limit 必须是正整数。")
        return 1
    sessions = list_research_sessions(args.research_dir, limit=args.limit)
    if not sessions:
        print("No research sessions found.")
        return 0
    print("Research Sessions:")
    for session in sessions:
        print(
            f"{session.get('research_id', '')} | {session.get('query', '')} | "
            f"evidence: {session.get('evidence_count', 0)} | "
            f"retriever: {session.get('retriever', '')} | "
            f"ingested: {str(session.get('ingested', False)).lower()}"
        )
    return 0


def research_show_command(args: argparse.Namespace) -> int:
    try:
        metadata, markdown = read_research_session_parts(args.research_id_or_path, args.research_dir)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Research session error: {exc}")
        return 1
    if args.metadata_only:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return 0
    if args.content_only:
        print(markdown)
        return 0
    print(f"research_id: {metadata.get('research_id', '')}")
    print(f"query: {metadata.get('query', '')}")
    print(f"created_at: {metadata.get('created_at', '')}")
    print(f"retriever: {metadata.get('retriever', '')}")
    print(f"evidence_count: {metadata.get('evidence_count', 0)}")
    print(f"ingested: {str(metadata.get('ingested', False)).lower()}")
    print("")
    print(markdown)
    return 0


def research_ingest_command(args: argparse.Namespace) -> int:
    if args.summary_only and args.details_only:
        print("research-ingest 参数错误：--summary-only 和 --details-only 不能同时使用。")
        return 1
    try:
        markdown_path = resolve_research_markdown_input(args.research_id_or_path, args.research_dir)
        candidates = ingest_report_file(
            str(markdown_path),
            include_summary_item=not args.details_only,
            include_detail_items=not args.summary_only,
        )
    except (OSError, ValueError) as exc:
        print(f"Research ingest error: {exc}")
        return 1
    should_apply = args.apply and not args.dry_run
    if not should_apply:
        print(f"[DRY RUN] Research report would be ingested: {markdown_path}")
        print(f"Candidates: {len(candidates)}")
        return 0
    result = import_records(candidates)
    print(f"Imported: {result.imported}")
    print(f"Skipped duplicates: {result.skipped_duplicates}")
    print(f"Failed: {result.failed}")
    for error in result.errors:
        print(error)
    if not Path(args.research_id_or_path).exists() and result.failed == 0:
        mark_research_ingested(args.research_id_or_path, research_dir=args.research_dir)
        print(f"Research session marked as ingested: {args.research_id_or_path}")
    return 0


def research_delete_command(args: argparse.Namespace) -> int:
    if not args.yes:
        print(f"This will delete research session: {args.research_id}")
        print("Re-run with --yes to confirm.")
        return 0
    result = delete_research_session(args.research_id, research_dir=args.research_dir)
    print(f"Deleted markdown: {str(result['deleted_markdown']).lower()}")
    print(f"Deleted metadata: {str(result['deleted_metadata']).lower()}")
    return 0


def research_search_command(args: argparse.Namespace) -> int:
    if args.top <= 0:
        print("research-search 参数错误：--top 必须是正整数。")
        return 1
    if args.ingested and args.not_ingested:
        print("research-search 参数错误：--ingested 和 --not-ingested 不能同时使用。")
        return 1
    ingested = True if args.ingested else False if args.not_ingested else None
    try:
        documents = build_research_documents(args.research_dir)
        results = search_research_documents(
            args.query,
            documents,
            top_k=args.top,
            retriever=args.retriever,
            ingested=ingested,
            since=args.since,
            until=args.until,
        )
    except ValueError as exc:
        print(f"research-search 参数错误：{exc}")
        return 1
    print(build_research_search_report(results, args.query))
    return 0


def research_stats_command(args: argparse.Namespace) -> int:
    documents = build_research_documents(args.research_dir)
    print(render_research_stats(build_research_collection_stats(documents)))
    return 0


def research_export_command(args: argparse.Namespace) -> int:
    if args.id and args.query:
        print("research-export 参数错误：Use either --id or --query, not both.")
        return 1
    if args.ingested and args.not_ingested:
        print("research-export 参数错误：--ingested 和 --not-ingested 不能同时使用。")
        return 1
    if args.top is not None and args.top <= 0:
        print("research-export 参数错误：--top 必须是正整数。")
        return 1

    ingested = True if args.ingested else False if args.not_ingested else None
    warnings = []
    try:
        sessions = select_research_sessions(
            research_dir=args.research_dir,
            query=args.query,
            research_ids=args.id,
            retriever=args.retriever,
            ingested=ingested,
            since=args.since,
            until=args.until,
            top_k=args.top,
        )
    except ValueError as exc:
        print(f"research-export 参数错误：{exc}")
        return 1

    if args.id:
        selected_ids = {str(session.get("research_id", "")) for session in sessions}
        for research_id in args.id:
            if research_id not in selected_ids:
                warnings.append(f"Research session not found: {research_id}")

    if not sessions:
        print("No research sessions selected.")
        return 0

    filters = {
        "research_ids": args.id or [],
        "retriever": args.retriever,
        "ingested": ingested,
        "since": args.since,
        "until": args.until,
        "top": args.top,
    }
    if not args.apply or args.dry_run:
        print(f"[DRY RUN] Research sessions selected: {len(sessions)}")
        for session in sessions:
            print(f"- {session.get('research_id', '')} | {session.get('query', '')}")
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"- {warning}")
        print(f"Output would be: {args.output}")
        return 0

    output_path = export_research_pack(
        sessions,
        args.output,
        export_name=args.name,
        query=args.query,
        filters=filters,
        warnings=warnings,
    )
    manifest = build_export_manifest(sessions, args.name, query=args.query, filters=filters, warnings=warnings)
    print(summarize_export_result(output_path, manifest))
    return 0


def research_import_command(args: argparse.Namespace) -> int:
    should_apply = args.apply and not args.dry_run
    try:
        result = import_research_pack(
            args.file,
            research_dir=args.research_dir,
            overwrite=args.overwrite,
            apply=should_apply,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"research-import error: {exc}")
        return 1
    if should_apply:
        print(summarize_import_result(result))
    else:
        print(render_import_plan(result["plan"]))
    return 0


def resolve_research_markdown_input(value: str, research_dir: str) -> Path:
    direct_path = Path(value)
    if direct_path.exists():
        return direct_path
    return resolve_research_path(value, research_dir, ".md")


def read_research_session_parts(value: str, research_dir: str) -> tuple[dict, str]:
    direct_path = Path(value)
    if direct_path.exists() and direct_path.suffix == ".json":
        metadata = read_research_metadata(str(direct_path), research_dir=research_dir)
        markdown = read_research_markdown(metadata.get("research_id", ""), research_dir=research_dir)
        return metadata, markdown
    if direct_path.exists() and direct_path.suffix == ".md":
        markdown = read_research_markdown(str(direct_path), research_dir=research_dir)
        metadata_path = direct_path.with_suffix(".json")
        metadata = read_research_metadata(str(metadata_path), research_dir=research_dir) if metadata_path.exists() else {}
        return metadata, markdown
    return (
        read_research_metadata(value, research_dir=research_dir),
        read_research_markdown(value, research_dir=research_dir),
    )


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

    report_ingest_parser = subparsers.add_parser("report-ingest", help="将 Markdown report 沉淀为本地 KB items")
    report_ingest_parser.add_argument("--file", required=True, help="Markdown report 文件路径")
    report_ingest_parser.add_argument("--summary-only", action="store_true", help="只沉淀整份报告 summary item")
    report_ingest_parser.add_argument("--details-only", action="store_true", help="只沉淀重点条目 detail items")
    report_ingest_parser.add_argument("--industry", default="AI", help="报告 summary item 默认行业，默认 AI")
    report_ingest_parser.add_argument("--dry-run", action="store_true", help="只打印候选 items，不写 CSV")
    report_ingest_parser.add_argument("--apply", action="store_true", help="写入 CSV")
    report_ingest_parser.set_defaults(func=report_ingest_command)

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
    pipeline_parser.add_argument("--ingest-report", action="store_true", help="报告生成后沉淀为本地 KB items")
    pipeline_parser.add_argument("--ingest-report-summary-only", action="store_true", help="pipeline report ingest 只沉淀 summary item")
    pipeline_parser.add_argument("--ingest-report-details-only", action="store_true", help="pipeline report ingest 只沉淀 detail items")
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

    ask_parser = subparsers.add_parser("ask", help="基于本地知识库检索问答")
    ask_parser.add_argument("query", help="问题")
    ask_parser.add_argument("--top", type=int, default=5, help="检索结果数量，默认 5")
    ask_parser.add_argument("--industry", help="按行业筛选")
    ask_parser.add_argument("--tag", help="按标签筛选")
    ask_parser.add_argument("--company", help="按公司/机构筛选")
    ask_parser.add_argument("--since", help="只检索 date >= since 的记录，格式 YYYY-MM-DD")
    ask_parser.add_argument("--until", help="只检索 date <= until 的记录，格式 YYYY-MM-DD")
    ask_parser.add_argument("--llm", action="store_true", help="显式调用 DeepSeek 综合回答")
    ask_parser.add_argument("--model", help="覆盖默认 DeepSeek 模型")
    ask_parser.add_argument("--show-sources", action="store_true", help="显示检索证据详情")
    citation_group = ask_parser.add_mutually_exclusive_group()
    citation_group.add_argument(
        "--citations",
        dest="citations",
        action="store_true",
        default=True,
        help="显示引用编号和证据列表，默认开启",
    )
    citation_group.add_argument(
        "--no-citations",
        dest="citations",
        action="store_false",
        help="关闭引用编号，使用接近旧版的简洁回答",
    )
    ask_parser.add_argument(
        "--retriever",
        choices=("keyword", "embedding", "fts"),
        default="keyword",
        help="检索器类型，默认 keyword",
    )
    ask_parser.set_defaults(func=ask_command)

    research_parser = subparsers.add_parser("research", help="围绕研究问题生成 Markdown 研究笔记")
    research_parser.add_argument("query", help="研究问题")
    research_parser.add_argument("--retriever", choices=("keyword", "embedding", "fts"), default="keyword", help="检索器类型，默认 keyword")
    research_parser.add_argument("--top", type=int, default=8, help="检索证据数量，默认 8")
    research_parser.add_argument("--industry", help="按行业筛选")
    research_parser.add_argument("--tag", help="按标签筛选")
    research_parser.add_argument("--company", help="按公司/机构筛选")
    research_parser.add_argument("--since", help="只检索 date >= since 的记录，格式 YYYY-MM-DD")
    research_parser.add_argument("--until", help="只检索 date <= until 的记录，格式 YYYY-MM-DD")
    research_parser.add_argument("--llm", action="store_true", help="显式调用 DeepSeek 综合分析")
    research_parser.add_argument("--model", help="覆盖默认 DeepSeek 模型")
    research_parser.add_argument("--output", default="outputs/research_session.md", help="输出 Markdown 路径，默认 outputs/research_session.md")
    research_parser.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    research_parser.add_argument("--apply", action="store_true", help="写入 Markdown 文件")
    research_parser.add_argument("--ingest", action="store_true", help="将 research report 沉淀回 KB")
    research_parser.add_argument("--ingest-summary-only", action="store_true", help="只沉淀 research report summary item")
    research_parser.add_argument("--ingest-details-only", action="store_true", help="只沉淀 detail items")
    research_parser.add_argument("--save-session", action="store_true", help="保存到 research collection")
    research_parser.add_argument("--research-dir", default="research", help="research collection 目录，默认 research")
    research_parser.add_argument("--research-id", help="指定 research session id")
    research_parser.set_defaults(func=research_command)

    research_list_parser = subparsers.add_parser("research-list", help="列出 research collection sessions")
    research_list_parser.add_argument("--research-dir", default="research", help="research collection 目录，默认 research")
    research_list_parser.add_argument("--limit", type=int, default=20, help="展示条数，默认 20")
    research_list_parser.set_defaults(func=research_list_command)

    research_show_parser = subparsers.add_parser("research-show", help="查看 research session")
    research_show_parser.add_argument("research_id_or_path", help="research_id 或 metadata/markdown 文件路径")
    research_show_parser.add_argument("--research-dir", default="research", help="research collection 目录，默认 research")
    show_group = research_show_parser.add_mutually_exclusive_group()
    show_group.add_argument("--metadata-only", action="store_true", help="只显示 metadata")
    show_group.add_argument("--content-only", action="store_true", help="只显示 Markdown 内容")
    research_show_parser.set_defaults(func=research_show_command)

    research_ingest_parser = subparsers.add_parser("research-ingest", help="将 research session 沉淀到 KB")
    research_ingest_parser.add_argument("research_id_or_path", help="research_id 或 Markdown 文件路径")
    research_ingest_parser.add_argument("--research-dir", default="research", help="research collection 目录，默认 research")
    research_ingest_parser.add_argument("--summary-only", action="store_true", help="只沉淀 summary item")
    research_ingest_parser.add_argument("--details-only", action="store_true", help="只沉淀 detail items")
    research_ingest_parser.add_argument("--dry-run", action="store_true", help="只预览，不写 CSV")
    research_ingest_parser.add_argument("--apply", action="store_true", help="写入 CSV")
    research_ingest_parser.set_defaults(func=research_ingest_command)

    research_delete_parser = subparsers.add_parser("research-delete", help="删除 research session")
    research_delete_parser.add_argument("research_id", help="research_id")
    research_delete_parser.add_argument("--research-dir", default="research", help="research collection 目录，默认 research")
    research_delete_parser.add_argument("--yes", action="store_true", help="确认删除")
    research_delete_parser.set_defaults(func=research_delete_command)

    research_search_parser = subparsers.add_parser("research-search", help="检索 research collection sessions")
    research_search_parser.add_argument("query", help="检索关键词")
    research_search_parser.add_argument("--research-dir", default="research", help="research collection 目录，默认 research")
    research_search_parser.add_argument("--top", type=int, default=10, help="展示结果数量，默认 10")
    research_search_parser.add_argument("--retriever", help="按 retriever 精确筛选")
    ingest_filter_group = research_search_parser.add_mutually_exclusive_group()
    ingest_filter_group.add_argument("--ingested", action="store_true", help="只显示已沉淀 sessions")
    ingest_filter_group.add_argument("--not-ingested", action="store_true", help="只显示未沉淀 sessions")
    research_search_parser.add_argument("--since", help="只检索 created_at 日期 >= since 的 sessions，格式 YYYY-MM-DD")
    research_search_parser.add_argument("--until", help="只检索 created_at 日期 <= until 的 sessions，格式 YYYY-MM-DD")
    research_search_parser.set_defaults(func=research_search_command)

    research_stats_parser = subparsers.add_parser("research-stats", help="查看 research collection 统计")
    research_stats_parser.add_argument("--research-dir", default="research", help="research collection 目录，默认 research")
    research_stats_parser.set_defaults(func=research_stats_command)

    research_export_parser = subparsers.add_parser("research-export", help="导出 research sessions 为 zip 研究包")
    research_export_parser.add_argument("--research-dir", default="research", help="research collection 目录，默认 research")
    research_export_parser.add_argument("--output", default="exports/research_pack.zip", help="输出 zip 路径，默认 exports/research_pack.zip")
    research_export_parser.add_argument("--name", default="research_pack", help="导出包名称，默认 research_pack")
    research_export_parser.add_argument("--query", help="按主题搜索 research sessions")
    research_export_parser.add_argument("--id", action="append", help="按 research_id 精确导出，可重复传入")
    research_export_parser.add_argument("--retriever", help="按 retriever 筛选")
    export_ingest_group = research_export_parser.add_mutually_exclusive_group()
    export_ingest_group.add_argument("--ingested", action="store_true", help="只导出已沉淀 sessions")
    export_ingest_group.add_argument("--not-ingested", action="store_true", help="只导出未沉淀 sessions")
    research_export_parser.add_argument("--since", help="只导出 created_at 日期 >= since 的 sessions，格式 YYYY-MM-DD")
    research_export_parser.add_argument("--until", help="只导出 created_at 日期 <= until 的 sessions，格式 YYYY-MM-DD")
    research_export_parser.add_argument("--top", type=int, help="限制导出数量")
    research_export_parser.add_argument("--dry-run", action="store_true", help="只预览，不写 zip")
    research_export_parser.add_argument("--apply", action="store_true", help="实际写 zip")
    research_export_parser.set_defaults(func=research_export_command)

    research_import_parser = subparsers.add_parser("research-import", help="从 research pack zip 导入 research sessions")
    research_import_parser.add_argument("--file", required=True, help="research pack zip 路径")
    research_import_parser.add_argument("--research-dir", default="research", help="research collection 目录，默认 research")
    research_import_parser.add_argument("--overwrite", action="store_true", help="允许覆盖本地已有同名 session")
    research_import_parser.add_argument("--dry-run", action="store_true", help="只展示导入计划，不写文件")
    research_import_parser.add_argument("--apply", action="store_true", help="实际导入 research session 文件")
    research_import_parser.set_defaults(func=research_import_command)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
