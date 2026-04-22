"""Raw sample rows → enriched, deterministic catalog records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EnrichedRecord:
    sku: str
    title: str


def _fixture_path() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "sample.json"


def load_sample_fixture() -> list[dict[str, str]]:
    with _fixture_path().open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("sample fixture must be a JSON array")
    return data


def enrich_records(raw: list[dict[str, str]]) -> list[EnrichedRecord]:
    """Map raw dicts to ``EnrichedRecord`` and sort by title for stable output."""
    records = [
        EnrichedRecord(sku=str(row["sku"]), title=str(row["title"]))
        for row in raw
    ]
    return sorted(records, key=lambda r: r.title.casefold())
