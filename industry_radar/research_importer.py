from __future__ import annotations

import json
import zipfile
from pathlib import Path


def inspect_research_pack(zip_path: str) -> dict:
    path = Path(zip_path)
    if not path.exists():
        raise FileNotFoundError(f"research pack not found: {zip_path}")
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.namelist()
            if "manifest.json" not in members:
                raise ValueError("research pack missing manifest.json")
            try:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"manifest.json is not valid JSON: {exc}") from exc
    except zipfile.BadZipFile as exc:
        raise ValueError(f"research pack is not a valid zip file: {zip_path}") from exc

    return {
        "zip_path": str(path),
        "manifest": validate_research_pack_manifest(manifest),
        "members": members,
        "research_markdown_files": [name for name in members if name.startswith("research/") and name.endswith(".md")],
        "research_metadata_files": [name for name in members if name.startswith("research/") and name.endswith(".json")],
    }


def validate_research_pack_manifest(manifest: dict) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    for key in ("export_name", "created_at", "session_count", "sessions"):
        if key not in manifest:
            raise ValueError(f"manifest missing required key: {key}")
    if not isinstance(manifest["sessions"], list):
        raise ValueError("manifest sessions must be a list")
    for index, session in enumerate(manifest["sessions"], start=1):
        if not isinstance(session, dict):
            raise ValueError(f"manifest session {index} must be an object")
        for key in ("research_id", "query", "metadata_path", "markdown_path"):
            if key not in session:
                raise ValueError(f"manifest session {index} missing required key: {key}")
    return manifest


def build_import_plan(
    pack_info: dict,
    research_dir: str = "research",
    overwrite: bool = False,
) -> dict:
    members = set(pack_info.get("members", []))
    base = Path(research_dir)
    sessions = []
    counts = {"new": 0, "exists": 0, "overwrite": 0, "missing_files": 0}

    for session in pack_info.get("manifest", {}).get("sessions", []):
        research_id = str(session.get("research_id", ""))
        markdown_member = str(session.get("markdown_path", f"research/{research_id}.md"))
        metadata_member = str(session.get("metadata_path", f"research/{research_id}.json"))
        target_markdown = base / f"{research_id}.md"
        target_metadata = base / f"{research_id}.json"

        if markdown_member not in members or metadata_member not in members:
            status = "missing_files"
            reason = "markdown or metadata file missing from pack"
        elif target_markdown.exists() or target_metadata.exists():
            status = "overwrite" if overwrite else "exists"
            reason = "local research session exists; overwrite enabled" if overwrite else "local research session exists"
        else:
            status = "new"
            reason = "new research session"

        counts[status] += 1
        sessions.append(
            {
                "research_id": research_id,
                "query": str(session.get("query", "")),
                "markdown_member": markdown_member,
                "metadata_member": metadata_member,
                "target_markdown": str(target_markdown),
                "target_metadata": str(target_metadata),
                "status": status,
                "reason": reason,
            }
        )

    return {
        "total": len(sessions),
        "new": counts["new"],
        "exists": counts["exists"],
        "overwrite": counts["overwrite"],
        "missing_files": counts["missing_files"],
        "sessions": sessions,
    }


def render_import_plan(plan: dict) -> str:
    lines = [
        "Research Pack Import Plan",
        "",
        f"Total sessions: {plan.get('total', 0)}",
        f"New: {plan.get('new', 0)}",
        f"Existing: {plan.get('exists', 0)}",
        f"Overwrite: {plan.get('overwrite', 0)}",
        f"Missing files: {plan.get('missing_files', 0)}",
        "",
        "Sessions:",
    ]
    sessions = plan.get("sessions", [])
    if not sessions:
        lines.append("No sessions found.")
        return "\n".join(lines)
    for session in sessions:
        lines.extend(
            [
                f"- {session.get('research_id', '')} | {session.get('query', '')}",
                f"  status: {session.get('status', '')}",
                f"  reason: {session.get('reason', '')}",
            ]
        )
    return "\n".join(lines)


def import_research_pack(
    zip_path: str,
    research_dir: str = "research",
    overwrite: bool = False,
    apply: bool = False,
) -> dict:
    pack_info = inspect_research_pack(zip_path)
    plan = build_import_plan(pack_info, research_dir=research_dir, overwrite=overwrite)
    result = {
        "zip_path": zip_path,
        "applied": bool(apply),
        "imported": 0,
        "skipped_existing": plan["exists"],
        "skipped_missing": plan["missing_files"],
        "overwritten": 0,
        "plan": plan,
    }
    if not apply:
        return result

    Path(research_dir).mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        for session in plan["sessions"]:
            if session["status"] not in {"new", "overwrite"}:
                continue
            markdown_bytes = archive.read(session["markdown_member"])
            metadata_bytes = archive.read(session["metadata_member"])
            Path(session["target_markdown"]).write_bytes(markdown_bytes)
            Path(session["target_metadata"]).write_bytes(metadata_bytes)
            if session["status"] == "overwrite":
                result["overwritten"] += 1
            else:
                result["imported"] += 1
    return result


def summarize_import_result(result: dict) -> str:
    return "\n".join(
        [
            "Research pack import summary",
            f"Applied: {str(result.get('applied', False)).lower()}",
            f"Imported: {result.get('imported', 0)}",
            f"Skipped existing: {result.get('skipped_existing', 0)}",
            f"Skipped missing: {result.get('skipped_missing', 0)}",
            f"Overwritten: {result.get('overwritten', 0)}",
        ]
    )
