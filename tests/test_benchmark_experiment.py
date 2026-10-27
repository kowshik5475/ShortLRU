import csv
from pathlib import Path
from benchmark import run_experiments, write_experiment_csv


def test_experiment_has_both_strategies_and_phase_rows(tmp_path: Path):
    rows = run_experiments(["hot_scan"], [2], [1], 1, ["lru", "second_access"],
                           window_size=3, requests=20, hot_set_size=2)
    overall = [r for r in rows if r["row_type"] == "overall"]
    assert {r["strategy"] for r in overall} == {"lru", "second_access"}
    assert all(r["hits"] + r["misses"] == r["requests"] for r in overall)
    assert any(r["phase"] == "post_scan_hot" for r in rows)
    output = tmp_path / "experiment.csv"
    write_experiment_csv(rows, output)
    with output.open(newline="", encoding="utf-8") as f:
        loaded = list(csv.DictReader(f))
    assert len(loaded) == len(rows)
