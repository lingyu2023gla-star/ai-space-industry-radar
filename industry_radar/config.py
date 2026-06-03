from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import normalize_industry, validate_date


PIPELINE_CONFIG_KEYS = {
    "sources",
    "limit",
    "industry",
    "since",
    "until",
    "top",
    "report",
    "enrich",
    "overwrite",
    "model",
}

PIPELINE_DEFAULTS = {
    "sources": None,
    "limit": 5,
    "industry": None,
    "since": None,
    "until": None,
    "top": None,
    "report": "outputs/pipeline_report.md",
    "enrich": False,
    "overwrite": False,
    "model": None,
}


def load_json_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        with config_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Config file is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a JSON object")
    return data


def validate_pipeline_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in config.items():
        if key not in PIPELINE_CONFIG_KEYS:
            raise ValueError(f"Unknown pipeline config key: {key}")
        if value is None:
            normalized[key] = None
            continue
        if key == "limit":
            normalized[key] = validate_positive_int(value, "limit")
        elif key == "top":
            normalized[key] = validate_positive_int(value, "top")
        elif key == "industry":
            normalized[key] = normalize_industry(str(value)) if value else None
        elif key in {"since", "until"}:
            normalized[key] = validate_date(str(value)) if value else None
        elif key in {"enrich", "overwrite"}:
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be a boolean")
            normalized[key] = value
        elif key in {"sources", "report", "model"}:
            if value and not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
            normalized[key] = value or None
    return normalized


def validate_positive_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def merge_pipeline_config(
    defaults: dict[str, Any],
    config: dict[str, Any],
    cli_overrides: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(defaults)
    merged.update(config)
    for key, value in cli_overrides.items():
        if value is None:
            continue
        merged[key] = value
    return merged
