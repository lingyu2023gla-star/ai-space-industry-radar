from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import uuid4


FIELDNAMES = [
    "id",
    "date",
    "industry",
    "category",
    "company",
    "title",
    "source",
    "source_url",
    "summary",
    "signal",
    "tags",
    "importance",
    "created_at",
    "updated_at",
]


KNOWN_PROMPT_FIELDS = {
    "category",
    "company",
    "industry",
    "importance",
    "signal",
    "source",
    "source url",
    "source_url",
    "summary",
    "tags",
    "title",
}

INDUSTRY_ALIASES = {
    "ai": "AI",
    "人工智能": "AI",
    "大模型": "AI",
    "llm": "AI",
    "commercial space": "Commercial Space",
    "space": "Commercial Space",
    "商业航天": "Commercial Space",
    "航天": "Commercial Space",
    "卫星": "Commercial Space",
}


def clean_prompt_value(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = value.strip()
    if not cleaned:
        return ""
    for separator in (":", "："):
        if separator not in cleaned:
            continue
        prefix, suffix = cleaned.split(separator, 1)
        field_name = prefix.split("[", 1)[0].strip().casefold()
        if field_name in KNOWN_PROMPT_FIELDS:
            return suffix.strip()
    return cleaned


def normalize_industry(value: str) -> str:
    cleaned = clean_prompt_value(value)
    normalized = INDUSTRY_ALIASES.get(cleaned.casefold())
    if normalized:
        return normalized
    raise ValueError("industry currently only supports AI and Commercial Space")


def normalize_importance(value: str) -> int:
    cleaned = clean_prompt_value(value)
    try:
        importance = int(cleaned)
    except ValueError as exc:
        raise ValueError("importance must be an integer between 1 and 5") from exc
    if 1 <= importance <= 5:
        return importance
    raise ValueError("importance must be an integer between 1 and 5")


def normalize_tags(value: str | None) -> str:
    cleaned = clean_prompt_value(value)
    if not cleaned:
        return ""
    normalized_separator = cleaned.replace("；", ";")
    tags = [tag.strip() for tag in normalized_separator.split(";")]
    return ";".join(tag for tag in tags if tag)


def validate_date(value: str | None) -> str:
    cleaned = clean_prompt_value(value)
    if not cleaned:
        return ""
    try:
        date.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format") from exc
    return cleaned


@dataclass(frozen=True)
class IndustryItem:
    id: str
    date: str
    industry: str
    category: str
    company: str
    title: str
    source: str
    source_url: str
    summary: str
    signal: str
    tags: str
    importance: int
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("id is required")
        if not self.date.strip():
            raise ValueError("date is required")
        validate_date(self.date)

        required_text_fields = [
            "industry",
            "category",
            "company",
            "title",
            "source",
            "summary",
        ]
        for field_name in required_text_fields:
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} is required")

        if not isinstance(self.importance, int):
            raise ValueError("importance must be an integer")
        if self.importance < 1 or self.importance > 5:
            raise ValueError("importance must be between 1 and 5")

    @classmethod
    def create(
        cls,
        *,
        industry: str,
        category: str,
        company: str,
        title: str,
        source: str,
        summary: str,
        signal: str,
        importance: int,
        source_url: str = "",
        tags: str = "",
    ) -> "IndustryItem":
        timestamp = datetime.now().replace(microsecond=0).isoformat()
        return cls(
            id=uuid4().hex,
            date=date.today().isoformat(),
            industry=normalize_industry(industry),
            category=clean_prompt_value(category),
            company=clean_prompt_value(company),
            title=clean_prompt_value(title),
            source=clean_prompt_value(source),
            source_url=clean_prompt_value(source_url),
            summary=clean_prompt_value(summary),
            signal=clean_prompt_value(signal),
            tags=normalize_tags(tags),
            importance=normalize_importance(str(importance)),
            created_at=timestamp,
            updated_at=timestamp,
        )

    @classmethod
    def from_import_record(cls, row: dict[str, Any]) -> "IndustryItem":
        timestamp = datetime.now().replace(microsecond=0).isoformat()
        data = {
            field: clean_prompt_value(str(row.get(field, "")))
            for field in FIELDNAMES
        }
        created_at = data["created_at"] or timestamp
        updated_at = data["updated_at"] or created_at
        item_id = data["id"] or uuid4().hex

        return cls(
            id=item_id,
            date=validate_date(data["date"]),
            industry=normalize_industry(data["industry"]),
            category=data["category"],
            company=data["company"],
            title=data["title"],
            source=data["source"],
            source_url=data["source_url"],
            summary=data["summary"],
            signal=data["signal"],
            tags=normalize_tags(data["tags"]),
            importance=normalize_importance(data["importance"]),
            created_at=created_at,
            updated_at=updated_at,
        )

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "IndustryItem":
        data = {
            field: clean_prompt_value(str(row.get(field, "")))
            for field in FIELDNAMES
        }
        try:
            importance = normalize_importance(data["importance"])
        except ValueError as exc:
            raise ValueError("importance must be an integer between 1 and 5") from exc
        try:
            industry = normalize_industry(data["industry"])
        except ValueError:
            industry = clean_prompt_value(data["industry"])

        return cls(
            id=data["id"],
            date=data["date"],
            industry=industry,
            category=data["category"],
            company=data["company"],
            title=data["title"],
            source=data["source"],
            source_url=data["source_url"],
            summary=data["summary"],
            signal=data["signal"],
            tags=normalize_tags(data["tags"]),
            importance=importance,
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    def to_row(self) -> dict[str, str]:
        return {
            "id": self.id,
            "date": self.date,
            "industry": self.industry,
            "category": self.category,
            "company": self.company,
            "title": self.title,
            "source": self.source,
            "source_url": self.source_url,
            "summary": self.summary,
            "signal": self.signal,
            "tags": self.tags,
            "importance": str(self.importance),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
