from pathlib import Path

from benchmark import write_csv


def test_benchmark_csv_writer(tmp_path: Path):
    path = tmp_path / "results.csv"
    write_csv(
        [
            {
                "capacity": 3,
                "hit_rate_percent": 10.5,
                "hits": 10,
                "misses": 90,
                "evictions": 87,
                "time_ms": 1.25,
            }
        ],
        path,
    )

    text = path.read_text(encoding="utf-8")
    assert "capacity,hit_rate_percent,hits,misses,evictions,time_ms" in text
    assert "3,10.5,10,90,87,1.25" in text
