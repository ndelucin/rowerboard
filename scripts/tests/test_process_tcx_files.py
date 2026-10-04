import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import process_tcx_files as pt  # noqa: E402

NS = 'xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"'


def s4_tcx(start_min=0):
    pts = "".join(
        f"<Trackpoint><Time>2026-09-15T18:{start_min:02d}:{4 * i:02d}Z</Time><DistanceMeters>{10 * i}</DistanceMeters>"
        f"<Cadence>20</Cadence><Extensions><Watts>120</Watts></Extensions></Trackpoint>" for i in range(15))
    return (f'<TrainingCenterDatabase {NS}><Activities><Activity><Lap StartTime="2026-09-15T18:{start_min:02d}:00Z">'
            f"<TotalTimeSeconds>60</TotalTimeSeconds><DistanceMeters>140</DistanceMeters><Calories>10</Calories>"
            f"<Track>{pts}</Track></Lap></Activity></Activities></TrainingCenterDatabase>")


def polar_tcx(start_min=0):
    pts = "".join(
        f"<Trackpoint><Time>2026-09-15T18:{start_min:02d}:{s:02d}Z</Time><HeartRateBpm><Value>130</Value></HeartRateBpm></Trackpoint>"
        for s in range(60))
    return (f'<TrainingCenterDatabase {NS}><Activities><Activity><Lap StartTime="2026-09-15T18:{start_min:02d}:00Z">'
            f"<Calories>10</Calories><Track>{pts}</Track></Lap></Activity></Activities></TrainingCenterDatabase>")


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    (root / "data" / ".keep").write_text("")
    (root / ".gitignore").write_text("input/\n")
    git(root.parent, "init", "-q", str(root))
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    dl = tmp_path / "Downloads"
    dl.mkdir()
    return root, dl


def test_classify(tmp_path):
    (tmp_path / "a.tcx").write_text(s4_tcx())
    (tmp_path / "b.tcx").write_text(polar_tcx())
    (tmp_path / "c.tcx").write_text("<nope")
    (tmp_path / "d.tcx").write_text(f'<TrainingCenterDatabase {NS}/>')
    assert pt.classify(tmp_path / "a.tcx") == "s4"
    assert pt.classify(tmp_path / "b.tcx") == "polar"
    assert pt.classify(tmp_path / "c.tcx") is None
    assert pt.classify(tmp_path / "d.tcx") is None


def test_dry_run_moves_nothing(repo):
    root, dl = repo
    (dl / "w.tcx").write_text(s4_tcx())
    (dl / "p.TCX").write_text(polar_tcx())
    assert pt.process(root, dl, 24, dry_run=True, push=False, run_tests=False) == 0
    assert (dl / "w.tcx").exists() and (dl / "p.TCX").exists()
    assert not (root / "input").exists()
    assert git(root, "log", "--oneline").count("\n") == 1


def test_full_flow_commits_once_then_idempotent(repo):
    root, dl = repo
    (dl / "w.tcx").write_text(s4_tcx())
    (dl / "p.tcx").write_text(polar_tcx())
    (dl / "notes.txt").write_text("x")
    assert pt.process(root, dl, 24, dry_run=False, push=False, run_tests=False) == 0
    assert not (dl / "w.tcx").exists() and (root / "input/data/s4/w.tcx").exists()
    assert (dl / "notes.txt").exists()
    assert git(root, "log", "-1", "--format=%s").strip() == "Nouvelle séance 2026-09-15"
    assert "data/index.json" in git(root, "show", "--name-only", "--format=", "HEAD")
    # 2e passage : rien à faire, pas de nouveau commit
    assert pt.process(root, dl, 24, dry_run=False, push=False, run_tests=False) == 0
    assert git(root, "log", "--oneline").count("\n") == 2


def test_single_file_makes_no_commit(repo, capsys):
    root, dl = repo
    (dl / "w.tcx").write_text(s4_tcx())
    pt.process(root, dl, 24, dry_run=False, push=False, run_tests=False)
    assert "Il manque l'export Polar" in capsys.readouterr().out
    assert git(root, "log", "--oneline").count("\n") == 1


def test_refuses_when_other_files_are_modified(repo):
    root, dl = repo
    (root / "README.md").write_text("modif")
    (dl / "w.tcx").write_text(s4_tcx())
    with pytest.raises(pt.ProcessError, match="README.md"):
        pt.process(root, dl, 24, dry_run=False, push=False, run_tests=False)
    assert (dl / "w.tcx").exists()  # rien n'a bougé


def test_old_files_are_ignored(repo):
    import os, time
    root, dl = repo
    f = dl / "old.tcx"
    f.write_text(s4_tcx())
    old = time.time() - 72 * 3600
    os.utime(f, (old, old))
    assert pt.collect(dl, root / "s4", root / "polar", 24, dry_run=False) == {"s4": [], "polar": []}
    assert f.exists()


def test_same_session_with_other_name_is_not_duplicated(repo):
    root, dl = repo
    (dl / "w.tcx").write_text(s4_tcx())
    (dl / "w (1).tcx").write_text(s4_tcx())
    moved = pt.collect(dl, root / "s4", root / "polar", 24, dry_run=False)
    assert len(moved["s4"]) == 1
    assert len(list((dl).glob("*.tcx"))) == 1  # la copie est laissée dans Downloads
