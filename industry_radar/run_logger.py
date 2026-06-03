from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


VALID_STEP_STATUSES = {"success", "partial_success", "failed", "skipped"}
SENSITIVE_KEYWORDS = ("api_key", "apikey", "token", "secret", "password")


def generate_run_id(command: str = "pipeline") -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    normalized_command = re.sub(r"[^A-Za-z0-9]+", "-", command).strip("-")
    return f"{timestamp}-{normalized_command or 'run'}"


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def create_run_log(command: str, mode: str, config: dict) -> dict[str, Any]:
    return {
        "run_id": generate_run_id(command),
        "command": command,
        "mode": mode,
        "started_at": now_iso(),
        "ended_at": None,
        "duration_seconds": None,
        "config": sanitize_config(config),
        "steps": [],
        "summary": {},
    }


def add_step(
    run_log: dict,
    name: str,
    status: str,
    metrics: dict | None = None,
    errors: list | None = None,
    details: dict | None = None,
) -> None:
    if status not in VALID_STEP_STATUSES:
        raise ValueError(f"invalid step status: {status}")
    step = {
        "name": name,
        "status": status,
        "metrics": metrics or {},
        "errors": errors or [],
    }
    if details is not None:
        step["details"] = details
    run_log.setdefault("steps", []).append(step)


def finalize_run_log(run_log: dict) -> dict:
    ended_at = now_iso()
    run_log["ended_at"] = ended_at
    run_log["duration_seconds"] = calculate_duration_seconds(
        run_log.get("started_at", ""),
        ended_at,
    )

    steps = run_log.get("steps", [])
    total_errors = sum(len(step.get("errors", [])) for step in steps)
    statuses = [step.get("status") for step in steps]
    if "failed" in statuses:
        status = "failed"
    elif "partial_success" in statuses or total_errors:
        status = "partial_success"
    else:
        status = "success"
    run_log["summary"] = {
        "status": status,
        "total_errors": total_errors,
    }
    return run_log


def write_run_log(run_log: dict, runs_dir: str = "runs") -> str:
    path = Path(runs_dir)
    path.mkdir(parents=True, exist_ok=True)
    output_path = path / f"{run_log['run_id']}.json"
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(run_log, file, ensure_ascii=False, indent=2)
    return str(output_path)


def list_run_logs(runs_dir: str = "runs", limit: int = 10) -> list[dict]:
    path = Path(runs_dir)
    if not path.exists():
        return []
    entries = sorted(path.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    runs = []
    for entry in entries[:limit]:
        try:
            run_log = read_run_log(str(entry), runs_dir=runs_dir)
        except (OSError, json.JSONDecodeError):
            continue
        summary = run_log.get("summary", {})
        runs.append(
            {
                "run_id": run_log.get("run_id", ""),
                "command": run_log.get("command", ""),
                "mode": run_log.get("mode", ""),
                "started_at": run_log.get("started_at", ""),
                "duration_seconds": run_log.get("duration_seconds"),
                "status": summary.get("status", ""),
                "total_errors": summary.get("total_errors", 0),
            }
        )
    return runs


def read_run_log(path_or_run_id: str, runs_dir: str = "runs") -> dict:
    direct_path = Path(path_or_run_id)
    if direct_path.exists():
        path = direct_path
    else:
        path = Path(runs_dir) / f"{path_or_run_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"run log not found: {path_or_run_id}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def sanitize_config(config: dict) -> dict:
    sanitized = {}
    for key, value in config.items():
        if any(keyword in key.casefold() for keyword in SENSITIVE_KEYWORDS):
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


def calculate_duration_seconds(started_at: str, ended_at: str) -> float | None:
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(ended_at)
    except ValueError:
        return None
    return round((end - start).total_seconds(), 2)
