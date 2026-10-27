from pathlib import Path
from benchmark import run_experiments, write_experiment_csv
from report import make_charts


def test_experiment_report_creates_charts(tmp_path: Path):
    rows = run_experiments(["hot_scan", "zipf", "popularity_shift"], [2, 4], [1], 1,
                           ["lru", "second_access"], requests=30, hot_set_size=2)
    csv_path = tmp_path / "experiment.csv"
    write_experiment_csv(rows, csv_path)
    output = tmp_path / "charts"
    make_charts(csv_path, output)
    assert (output / "hit_rate_by_capacity.png").exists()
    assert (output / "post_scan_hit_rate.png").exists()
