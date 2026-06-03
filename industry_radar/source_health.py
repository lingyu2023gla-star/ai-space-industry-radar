from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import clean_prompt_value
from .run_logger import read_run_log


SOURCE_ERROR_RE = re.compile(r"^Source\s+([^:]+):\s*(.*)$")


def collect_source_health(run_logs: list[dict]) -> dict[str, dict[str, Any]]:
    health: dict[str, dict[str, Any]] = {}
    for run_log in run_logs:
        fetch_step = find_fetch_step(run_log)
        if fetch_step is None:
            continue
        seen_sources: set[str] = set()
        for error in fetch_step.get("errors", []):
            source, message = parse_source_error(error)
            if not source:
                continue
            entry = ensure_health_entry(health, source)
            if source not in seen_sources:
                entry["runs_seen"] += 1
                entry["failures"] += 1
            entry["last_error"] = message
            entry["last_status"] = "failed"
            seen_sources.add(source)

        for source_result in fetch_step.get("metrics", {}).get("sources", []):
            source = clean_prompt_value(str(source_result.get("source", "")))
            if not source or source in seen_sources:
                continue
            entry = ensure_health_entry(health, source)
            entry["runs_seen"] += 1
            status = clean_prompt_value(str(source_result.get("status", ""))) or "success"
            if status == "success":
                entry["successes"] += 1
            else:
                entry["failures"] += 1
                entry["last_error"] = clean_prompt_value(str(source_result.get("error", "")))
            entry["last_status"] = status

    for entry in health.values():
        runs_seen = entry["runs_seen"]
        entry["successes"] = max(0, runs_seen - entry["failures"])
        entry["failure_rate"] = entry["failures"] / runs_seen if runs_seen else 0.0
    return health


def load_run_logs_for_health(runs_dir: str = "runs", limit: int = 20) -> list[dict]:
    path = Path(runs_dir)
    if not path.exists():
        return []
    entries = sorted(path.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    run_logs = []
    for entry in entries[:limit]:
        try:
            run_log = read_run_log(str(entry), runs_dir=runs_dir)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(run_log, dict):
            run_logs.append(run_log)
    return run_logs


def load_source_names_from_config(sources_path: str | None) -> list[str]:
    if not sources_path:
        return []
    path = Path(sources_path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    names = []
    for source in data:
        if not isinstance(source, dict):
            continue
        name = clean_prompt_value(str(source.get("name", "")))
        if name:
            names.append(name)
    return names


def build_source_health_report(health: dict[str, dict[str, Any]]) -> str:
    lines = ["Source Health Summary", ""]
    if not health:
        lines.append("No source health data found.")
        return "\n".join(lines)

    entries = sorted(
        health.values(),
        key=lambda item: (-float(item.get("failure_rate", 0.0)), item.get("source", "")),
    )
    for entry in entries:
        lines.append(str(entry["source"]))
        lines.append(f"- runs: {entry['runs_seen']}")
        lines.append(f"- failures: {entry['failures']}")
        lines.append(f"- failure_rate: {entry['failure_rate'] * 100:.1f}%")
        lines.append(f"- last_status: {entry['last_status']}")
        if entry.get("last_error"):
            lines.append(f"- last_error: {entry['last_error']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def add_config_sources_to_health(
    health: dict[str, dict[str, Any]],
    source_names: list[str],
    runs_seen: int,
) -> dict[str, dict[str, Any]]:
    for source in source_names:
        if source in health:
            continue
        entry = ensure_health_entry(health, source)
        entry["runs_seen"] = runs_seen
        entry["successes"] = runs_seen
        entry["failures"] = 0
        entry["failure_rate"] = 0.0
        entry["last_status"] = "success" if runs_seen else "unknown"
    return health


def find_fetch_step(run_log: dict) -> dict | None:
    for step in run_log.get("steps", []):
        if step.get("name") == "fetch":
            return step
    return None


def parse_source_error(error: Any) -> tuple[str, str]:
    if isinstance(error, dict):
        source = clean_prompt_value(str(error.get("source", "")))
        message = clean_prompt_value(str(error.get("message", "")))
        return source, message
    text = clean_prompt_value(str(error))
    match = SOURCE_ERROR_RE.match(text)
    if match:
        return clean_prompt_value(match.group(1)), clean_prompt_value(match.group(2))
    return "", text


def ensure_health_entry(
    health: dict[str, dict[str, Any]],
    source: str,
) -> dict[str, Any]:
    if source not in health:
        health[source] = {
            "source": source,
            "runs_seen": 0,
            "failures": 0,
            "successes": 0,
            "failure_rate": 0.0,
            "last_error": "",
            "last_status": "success",
        }
    return health[source]
