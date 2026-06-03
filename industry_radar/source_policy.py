from __future__ import annotations

from copy import deepcopy
from typing import Any


def should_skip_source(
    source_name: str,
    health: dict,
    failure_rate_threshold: float = 0.8,
    min_runs: int = 3,
) -> tuple[bool, str]:
    validate_policy_params(failure_rate_threshold, min_runs)
    if source_name not in health:
        return False, "no health history"
    source_health = health[source_name]
    runs_seen = int(source_health.get("runs_seen", 0))
    if runs_seen < min_runs:
        return False, "insufficient history"
    failure_rate = float(source_health.get("failure_rate", 0.0))
    if failure_rate >= failure_rate_threshold:
        return (
            True,
            f"failure_rate {failure_rate * 100:.1f}% >= threshold "
            f"{failure_rate_threshold * 100:.1f}%",
        )
    return False, "healthy enough"


def filter_sources_by_health(
    sources: list[dict],
    health: dict,
    failure_rate_threshold: float = 0.8,
    min_runs: int = 3,
) -> tuple[list[dict], list[dict]]:
    validate_policy_params(failure_rate_threshold, min_runs)
    active_sources = []
    skipped_sources = []
    for source in sources:
        name = str(source.get("name", ""))
        should_skip, reason = should_skip_source(
            name,
            health,
            failure_rate_threshold=failure_rate_threshold,
            min_runs=min_runs,
        )
        if should_skip:
            source_health = health.get(name, {})
            skipped_sources.append(
                {
                    "name": name,
                    "reason": reason,
                    "failure_rate": float(source_health.get("failure_rate", 0.0)),
                    "runs_seen": int(source_health.get("runs_seen", 0)),
                }
            )
        else:
            active_sources.append(deepcopy(source))
    return active_sources, skipped_sources


def validate_policy_params(failure_rate_threshold: float, min_runs: int) -> None:
    if isinstance(failure_rate_threshold, bool) or not isinstance(
        failure_rate_threshold, (int, float)
    ):
        raise ValueError("failure_rate_threshold must be between 0 and 1")
    if failure_rate_threshold < 0 or failure_rate_threshold > 1:
        raise ValueError("failure_rate_threshold must be between 0 and 1")
    if not isinstance(min_runs, int) or isinstance(min_runs, bool) or min_runs <= 0:
        raise ValueError("min_runs must be a positive integer")
