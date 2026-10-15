"""Regression: synth.make(write=False) must never touch data/synthetic/.

Before this guard, tests/conftest.py called synth.make(..., write=False) which
unconditionally wrote records.parquet, truth.parquet and
ground_truth_incidents.json to data/synthetic/. Every pytest run therefore
clobbered the 45,863-row production dataset with a 5,742-row fixture,
collapsing macro F1 in reports/metrics.json from 0.7779 to 0.0315.
"""
import pytest
from storesignal import synth
from storesignal.config import ROOT

TARGET = ROOT / "data" / "synthetic" / "truth.parquet"


@pytest.mark.skipif(not TARGET.exists(), reason="no baseline to protect")
def test_make_no_write_leaves_files_untouched():
    before_ns = TARGET.stat().st_mtime_ns
    before_sz = TARGET.stat().st_size
    synth.make(days=2, n_stores=2, incidents=[], write=False)
    after_ns = TARGET.stat().st_mtime_ns
    after_sz = TARGET.stat().st_size
    assert before_ns == after_ns, f"mtime changed: {before_ns} -> {after_ns}"
    assert before_sz == after_sz, f"size changed: {before_sz} -> {after_sz}"
