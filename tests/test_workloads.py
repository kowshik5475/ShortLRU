from shortlru.workloads import hot_scan, popularity_shift, zipf_hotset


def test_seeded_zipf_repeats():
    assert zipf_hotset(seed=9) == zipf_hotset(seed=9)
    assert zipf_hotset(seed=9).codes != zipf_hotset(seed=10).codes


def test_hot_scan_phases_and_unique_scan():
    trace = hot_scan(capacity=4, hot_set_size=3, scan_factor=2, hot_requests=20, seed=3)
    scan = trace.phases[1]
    scan_codes = trace.codes[scan.start:scan.end]
    assert len(scan_codes) == len(set(scan_codes)) == 8
    assert set(trace.codes[:trace.phases[0].end]).isdisjoint(scan_codes)
    assert set(scan_codes).isdisjoint(trace.codes[scan.end:])


def test_popularity_shift_disjoint_sets_and_lengths():
    trace = popularity_shift(hot_set_size=5, requests_per_phase=30, seed=2)
    a, b = trace.phases
    assert a.length == b.length == 30
    assert set(trace.codes[a.start:a.end]).isdisjoint(trace.codes[b.start:b.end])


def test_invalid_workload_parameters():
    import pytest
    with pytest.raises(ValueError): zipf_hotset(url_count=0)
    with pytest.raises(ValueError): zipf_hotset(alpha=-1)
    with pytest.raises(ValueError): hot_scan(capacity=0)
    with pytest.raises(ValueError): popularity_shift(hot_set_size=0)
