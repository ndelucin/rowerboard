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
    git(root, "config", "commit.gpgsign", "false")
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


def test_failing_tests_never_let_a_rerun_commit(repo, monkeypatch):
    """H1 : si les tests échouent, la relance (séance déjà fusionnée) ne doit pas commiter sans tests."""
    root, dl = repo
    (dl / "w.tcx").write_text(s4_tcx())
    (dl / "p.tcx").write_text(polar_tcx())

    def failing(_root):
        raise pt.ProcessError("tests rouges")

    monkeypatch.setattr(pt, "run_pytest", failing)
    for _ in range(2):  # 1er passage : fusion puis échec ; 2e passage : data/ déjà modifié
        with pytest.raises(pt.ProcessError, match="tests rouges"):
            pt.process(root, dl, 24, dry_run=False, push=False)
    assert git(root, "log", "--oneline").count("\n") == 1


def test_malformed_tcx_is_ignored_and_does_not_break_merge(repo, capsys):
    """H2 : un TCX classé s4 mais sans heure de début reste dans Downloads et ne bloque pas la fusion."""
    root, dl = repo
    bad = s4_tcx().replace(' StartTime="2026-09-15T18:00:00Z"', "")
    (dl / "bad.tcx").write_text(bad)
    (dl / "w.tcx").write_text(s4_tcx())
    (dl / "p.tcx").write_text(polar_tcx())
    assert pt.process(root, dl, 24, dry_run=False, push=False, run_tests=False) == 0
    assert (dl / "bad.tcx").exists() and not (root / "input/data/s4/bad.tcx").exists()
    assert "bad.tcx" in capsys.readouterr().err
    assert git(root, "log", "-1", "--format=%s").strip() == "Nouvelle séance 2026-09-15"


def test_same_name_other_session_is_renamed_not_dropped(repo):
    """H3 : même nom de fichier mais autre séance → rangée sous un nom suffixé de son heure de début."""
    root, dl = repo
    (dl / "workout.tcx").write_text(s4_tcx(0))
    pt.collect(dl, root / "s4", root / "polar", 24, dry_run=False)
    (dl / "workout.tcx").write_text(s4_tcx(30))
    moved = pt.collect(dl, root / "s4", root / "polar", 24, dry_run=False)
    assert moved["s4"] == ["workout.tcx"]
    assert not (dl / "workout.tcx").exists()
    assert sorted(p.name for p in (root / "s4").glob("*.tcx")) == ["workout.tcx", "workout_20260915T183000.tcx"]


def test_unpushed_commit_is_pushed_on_next_run(repo, tmp_path):
    """M1 : un commit resté local (push échoué ou --no-push) est poussé à l'exécution suivante."""
    root, dl = repo
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-q", "-u", "origin", "HEAD")
    (dl / "w.tcx").write_text(s4_tcx())
    (dl / "p.tcx").write_text(polar_tcx())
    pt.process(root, dl, 24, dry_run=False, push=False, run_tests=False)
    assert pt.unpushed_count(root) == 1
    assert pt.process(root, dl, 24, dry_run=False, push=True, run_tests=False) == 0  # « rien de nouveau »
    assert pt.unpushed_count(root) == 0
    assert git(remote, "log", "-1", "--format=%s").strip() == "Nouvelle séance 2026-09-15"
