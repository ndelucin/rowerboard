import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merge_tcx as m  # noqa: E402

S4 = m.DEFAULT_S4_DIR
POLAR = m.DEFAULT_POLAR_DIR
needs_input = pytest.mark.skipif(not S4.exists(), reason="input/ absent")


@needs_input
def test_session_1509_matches_prototype_seed():
    s = m.compute_session(
        m.parse_s4(S4 / "2026-09-15_1807_workout.tcx"),
        m.parse_polar(POLAR / "Nicolas_Delucinge_2026-09-15_20-08-32.TCX"), 180)
    sm = s["summary"]
    assert s["id"] == "2026-09-15T18:07:17Z"
    assert sm["duration"] == pytest.approx(1072.275)
    assert sm["distance"] == 4025
    assert sm["avgHr"] == pytest.approx(124.37, abs=0.01)
    assert sm["avgWatts"] == pytest.approx(115.86, abs=0.01)
    assert sm["avgPace500"] == pytest.approx(133.2, abs=0.01)
    assert sm["zonePct"] == [11, 41, 48, 0, 0]
    assert not s["overlapWarning"]
    # la FC Polar démarre ~76 s après le S4 : pas de FC au début
    assert s["series"][0]["hr"] is None


@needs_input
def test_auto_pairs_match_by_date():
    pairs = m.auto_pairs(S4, POLAR)
    assert len(pairs) == 3
    for s4, polar in pairs:
        assert s4.name[:10] in polar.name


@needs_input
def test_write_is_idempotent(tmp_path):
    for _ in range(2):
        for s4, polar in m.auto_pairs(S4, POLAR):
            m.write_session(m.compute_session(m.parse_s4(s4), m.parse_polar(polar), 180), tmp_path)
    idx = json.loads((tmp_path / "index.json").read_text())
    assert [e["date"][:10] for e in idx["sessions"]] == ["2026-09-15", "2026-09-18", "2026-09-23"]
    assert len(list((tmp_path / "sessions").glob("*.json"))) == 3


def test_nearest_hr_tolerance():
    from datetime import datetime, timezone
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pts = [(t0, 100.0)]
    ts = [t0.timestamp()]
    assert m.nearest_hr(pts, ts, t0) == 100.0
    assert m.nearest_hr(pts, ts, datetime.fromtimestamp(t0.timestamp() + 16, timezone.utc)) is None


def test_invalid_xml(tmp_path):
    bad = tmp_path / "bad.tcx"
    bad.write_text("<nope")
    with pytest.raises(ValueError):
        m.parse_s4(bad)
