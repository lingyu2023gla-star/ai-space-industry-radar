from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .data_governance import DedupeResult, dedupe_items
from .enricher import (
    build_enrichment_prompt,
    merge_enrichment,
    needs_enrichment,
    parse_enrichment_result,
)
from .fetcher import FetchResult, fetch_and_import
from .fetcher import fetch_and_import_from_sources, load_sources
from .llm_client import call_deepseek_chat
from .models import IndustryItem, normalize_industry
from .report import write_report
from .run_logger import add_step, create_run_log, finalize_run_log, write_run_log
from .source_health import collect_source_health, load_run_logs_for_health
from .source_policy import filter_sources_by_health, validate_policy_params
from .storage import filter_items, read_items, write_items
from .storage_backend import StorageBackend


@dataclass
class PipelineEnrichResult:
    selected: int = 0
    enriched: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    mode: str
    fetch_result: FetchResult | None = None
    dedupe_result: DedupeResult | None = None
    enrich_result: PipelineEnrichResult | None = None
    report_path: Path | None = None
    report_written: bool = False
    run_log: dict | None = None
    run_log_path: str | None = None
    skipped_sources: list[dict] = field(default_factory=list)
    active_source_count: int = 0


def run_pipeline(
    *,
    sources_path: Path | None = None,
    limit: int = 5,
    industry: str | None = None,
    since: str | None = None,
    until: str | None = None,
    report_path: Path,
    top: int | None = None,
    enrich: bool = False,
    overwrite: bool = False,
    apply: bool = False,
    model: str | None = None,
    storage: StorageBackend | None = None,
    save_run_log: bool = False,
    runs_dir: str = "runs",
    skip_unhealthy_sources: bool = False,
    failure_rate_threshold: float = 0.8,
    min_source_runs: int = 3,
) -> PipelineResult:
    if limit <= 0:
        raise ValueError("--limit must be a positive integer")
    if top is not None and top <= 0:
        raise ValueError("--top must be a positive integer")
    validate_policy_params(failure_rate_threshold, min_source_runs)

    result = PipelineResult(mode="apply" if apply else "dry-run")
    run_log = create_run_log(
        "pipeline",
        result.mode,
        {
            "sources": str(sources_path) if sources_path else None,
            "limit": limit,
            "industry": industry,
            "since": since,
            "until": until,
            "report": str(report_path),
            "top": top,
            "enrich": enrich,
            "overwrite": overwrite,
            "model": model,
            "skip_unhealthy_sources": skip_unhealthy_sources,
            "failure_rate_threshold": failure_rate_threshold,
            "min_source_runs": min_source_runs,
            "runs_dir": runs_dir,
        },
    )
    result.run_log = run_log

    if sources_path is not None:
        if skip_unhealthy_sources:
            sources = load_sources(sources_path)
            if industry:
                industry_value = normalize_industry(industry)
                sources = [source for source in sources if source["industry"] == industry_value]
            health = collect_source_health(load_run_logs_for_health(runs_dir))
            active_sources, skipped_sources = filter_sources_by_health(
                sources,
                health,
                failure_rate_threshold=failure_rate_threshold,
                min_runs=min_source_runs,
            )
            result.skipped_sources = skipped_sources
            result.active_source_count = len(active_sources)
            add_step(
                run_log,
                "source_policy",
                "success",
                metrics={
                    "enabled": True,
                    "threshold": failure_rate_threshold,
                    "min_runs": min_source_runs,
                    "skipped_sources": len(skipped_sources),
                    "active_sources": len(active_sources),
                },
                details={"skipped": skipped_sources},
            )
            result.fetch_result = fetch_and_import_from_sources(
                active_sources,
                limit=limit,
                dry_run=not apply,
            )
        else:
            result.fetch_result = fetch_and_import(
                sources_path,
                limit=limit,
                industry=industry,
                dry_run=not apply,
            )
        add_step(
            run_log,
            "fetch",
            status_from_failed_count(result.fetch_result.failed),
            metrics={
                "fetched": result.fetch_result.fetched,
                "imported": result.fetch_result.imported,
                "skipped_duplicates": result.fetch_result.skipped_duplicates,
                "failed": result.fetch_result.failed,
                "source_count": result.fetch_result.source_count,
                "failed_sources": result.fetch_result.failed_sources,
            },
            errors=result.fetch_result.errors,
        )
    else:
        add_step(
            run_log,
            "fetch",
            "skipped",
            metrics={"reason": "sources not provided"},
        )

    current_items = _read_pipeline_items(storage)
    result.dedupe_result = dedupe_items(current_items)
    add_step(
        run_log,
        "dedupe",
        "success",
        metrics={
            "duplicate_groups": result.dedupe_result.duplicate_groups,
            "removed_duplicates": result.dedupe_result.removed_duplicates,
            "remaining_items": result.dedupe_result.remaining_items,
        },
    )
    if apply:
        _write_pipeline_items(result.dedupe_result.items, storage)
        current_items = result.dedupe_result.items

    if enrich:
        result.enrich_result = run_enrich_step(
            current_items,
            limit=limit,
            industry=industry,
            since=since,
            until=until,
            overwrite=overwrite,
            apply=apply,
            model=model,
            storage=storage,
        )
        add_step(
            run_log,
            "enrich",
            status_from_failed_count(result.enrich_result.failed),
            metrics={
                "selected": result.enrich_result.selected,
                "enriched": result.enrich_result.enriched,
                "skipped": result.enrich_result.skipped,
                "failed": result.enrich_result.failed,
            },
            errors=result.enrich_result.errors,
        )
        if apply:
            current_items = _read_pipeline_items(storage)
    else:
        add_step(
            run_log,
            "enrich",
            "skipped",
            metrics={"reason": "enrich disabled"},
        )

    report_items = filter_items(current_items, industry=industry, since=since, until=until)
    result.report_path = report_path
    if apply:
        write_report(report_items, report_path, top=top)
        result.report_written = True
    add_step(
        run_log,
        "report",
        "success",
        metrics={
            "output": str(report_path),
            "top": top,
            "industry": industry,
            "written": result.report_written,
        },
    )
    finalize_run_log(run_log)
    if save_run_log:
        result.run_log_path = write_run_log(run_log, runs_dir=runs_dir)
    return result


def run_enrich_step(
    items: list[IndustryItem],
    *,
    limit: int,
    industry: str | None = None,
    since: str | None = None,
    until: str | None = None,
    overwrite: bool = False,
    apply: bool = False,
    model: str | None = None,
    storage: StorageBackend | None = None,
) -> PipelineEnrichResult:
    selected = filter_items(items, industry=industry, since=since, until=until)[:limit]
    result = PipelineEnrichResult(selected=len(selected))
    enriched_by_id: dict[str, IndustryItem] = {}

    for item in selected:
        if not needs_enrichment(item, overwrite=overwrite):
            result.skipped += 1
            continue
        try:
            content = call_deepseek_chat(build_enrichment_prompt(item), model=model)
            enrichment = parse_enrichment_result(content)
            enriched_by_id[item.id] = merge_enrichment(
                item,
                enrichment,
                overwrite=overwrite,
            )
            result.enriched += 1
        except ValueError as exc:
            result.failed += 1
            result.errors.append(f"{item.title}: {exc}")

    if apply and enriched_by_id:
        updated_items = [enriched_by_id.get(item.id, item) for item in items]
        _write_pipeline_items(updated_items, storage)
    return result


def _read_pipeline_items(storage: StorageBackend | None) -> list[IndustryItem]:
    if storage is not None:
        return storage.read_items()
    return read_items()


def _write_pipeline_items(
    items: list[IndustryItem],
    storage: StorageBackend | None,
) -> None:
    if storage is not None:
        storage.write_items(items)
        return
    write_items(items)


def status_from_failed_count(failed: int) -> str:
    return "partial_success" if failed else "success"
