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
from .llm_client import call_deepseek_chat
from .models import IndustryItem
from .report import write_report
from .storage import filter_items, read_items, write_items


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
) -> PipelineResult:
    if limit <= 0:
        raise ValueError("--limit must be a positive integer")
    if top is not None and top <= 0:
        raise ValueError("--top must be a positive integer")

    result = PipelineResult(mode="apply" if apply else "dry-run")

    if sources_path is not None:
        result.fetch_result = fetch_and_import(
            sources_path,
            limit=limit,
            industry=industry,
            dry_run=not apply,
        )

    current_items = read_items()
    result.dedupe_result = dedupe_items(current_items)
    if apply:
        write_items(result.dedupe_result.items)
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
        )
        if apply:
            current_items = read_items()

    report_items = filter_items(current_items, industry=industry, since=since, until=until)
    result.report_path = report_path
    if apply:
        write_report(report_items, report_path, top=top)
        result.report_written = True
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
        write_items(updated_items)
    return result
