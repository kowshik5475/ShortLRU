from pathlib import Path

import pytest

from shortlru.dataset import load_urls


def test_load_urls(tmp_path: Path):
    path = tmp_path / "urls.csv"
    path.write_text(
        "url,category\n"
        "https://example.com,a\n"
        "https://python.org,programming\n"
        ",ignored\n",
        encoding="utf-8",
    )

    records = load_urls(path)

    assert len(records) == 2
    assert records[0].url == "https://example.com"
    assert records[0].category == "a"


def test_missing_dataset():
    with pytest.raises(FileNotFoundError):
        load_urls("does-not-exist.csv")


def test_missing_url_column(tmp_path: Path):
    path = tmp_path / "bad.csv"
    path.write_text("name\nexample\n", encoding="utf-8")

    with pytest.raises(ValueError, match="url"):
        load_urls(path)
