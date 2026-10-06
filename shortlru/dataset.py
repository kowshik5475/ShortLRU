"""Utilities for loading URL datasets used by ShortLRU demos and benchmarks."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DatasetURL:
    """A URL and its optional category."""

    url: str
    category: str


def load_urls(path: str | Path) -> list[DatasetURL]:
    """Load URL records from a CSV file.

    The CSV must contain a ``url`` column. A ``category`` column is optional.
    Empty URLs are ignored.
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"dataset not found: {csv_path}")

    records: list[DatasetURL] = []
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or "url" not in reader.fieldnames:
            raise ValueError("dataset must contain a 'url' column")

        for row in reader:
            url = (row.get("url") or "").strip()
            if not url:
                continue
            category = (row.get("category") or "uncategorized").strip()
            records.append(DatasetURL(url=url, category=category))

    return records
