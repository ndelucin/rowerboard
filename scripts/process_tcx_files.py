#!/usr/bin/env python3
"""Ramasse les TCX exportés (~/Downloads), fusionne, puis commit + push data/.

Usage typique après une séance : exporter le TCX sur waterrowernohrdaccount.com et sur Polar Flow,
puis lancer `python3 scripts/process_tcx_files.py`.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merge_tcx as m  # noqa: E402

SITE_URL = "https://ndelucin.github.io/rowerboard/"
DEFAULT_DOWNLOADS = Path.home() / "Downloads"
DEFAULT_SINCE_H = 24.0


class ProcessError(Exception):
    """Arrêt propre : le message est affiché tel quel."""


# --- Classement des fichiers ------------------------------------------------

def classify(path: Path) -> str | None:
    """'s4' (contient des Watts), 'polar' (FC sans Watts) ou None (pas un TCX exploitable)."""
    try:
        names = {m._local(e.tag) for e in ET.parse(path).getroot().iter()}
    except (ET.ParseError, OSError):
        return None
    if "Trackpoint" not in names:
        return None
    if "Watts" in names:
        return "s4"
    return "polar" if "HeartRateBpm" in names else None


def _start(path: Path):
    try:
        return m._start_of(path)
    except (ValueError, KeyError, OSError):
        return None


def _starts(directory: Path) -> set:
    """Heures de début des TCX déjà rangés (identifie une séance quel que soit le nom du fichier)."""
    return {t for t in (_start(p) for p in directory.glob("*.[tT][cC][xX]")) if t} if directory.is_dir() else set()


def collect(downloads: Path, s4_dir: Path, polar_dir: Path, since_h: float, dry_run: bool):
    """Déplace les TCX récents de `downloads` vers les dossiers d'entrée. Retourne {'s4': [...], 'polar': [...]}."""
    moved = {"s4": [], "polar": []}
    if not downloads.is_dir():
        raise ProcessError(f"Dossier introuvable : {downloads}")
    limit = time.time() - since_h * 3600
    for p in sorted(downloads.glob("*.[tT][cC][xX]")):
        if p.stat().st_mtime < limit:
            continue
        kind = classify(p)
        if kind is None:
            print(f"! Ignoré (TCX non reconnu) : {p.name}", file=sys.stderr)
            continue
        dest_dir = s4_dir if kind == "s4" else polar_dir
        dest = dest_dir / p.name
        if dest.exists() or _start(p) in _starts(dest_dir):
            print(f"= Déjà présent (même séance), laissé dans {downloads.name}/ : {p.name}")
            continue
        print(f"→ {kind:5} {p.name}")
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), dest)
        moved[kind].append(p.name)
    return moved


# --- Git --------------------------------------------------------------------

def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        raise ProcessError(f"git {' '.join(args)} a échoué :\n{r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def dirty_paths(root: Path) -> list[str]:
    """Fichiers modifiés ou non suivis (hors fichiers ignorés)."""
    return [l[3:] for l in git(root, "status", "--porcelain").splitlines()]


def outside_data(paths: list[str], data_rel: str) -> list[str]:
    return [p for p in paths if not (p.strip('"') + "/").startswith(data_rel + "/")]


# --- Rapport ----------------------------------------------------------------

def load_index(data_dir: Path) -> dict:
    p = data_dir / "index.json"
    if not p.exists():
        return {}
    return {e["id"]: e for e in json.loads(p.read_text(encoding="utf-8")).get("sessions", [])}


def describe(e: dict) -> str:
    d = e["date"][:10]
    pace = e.get("avgPace500")
    p2000 = f"{int(pace * 4 // 60)}:{int(pace * 4 % 60):02d}" if pace else "–"
    return f"{d[8:]}/{d[5:7]}/{d[2:4]} · {int(e['duration'] // 60)}:{int(e['duration'] % 60):02d} · {e['distance']:.0f} m · {p2000} /2000 m"


def run_pytest(root: Path) -> None:
    exe = root / ".venv" / "bin" / "pytest"
    if not exe.exists():
        print("! .venv absent : tests non lancés")
        return
    r = subprocess.run([str(exe), "-q", "scripts"], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        raise ProcessError("Les tests échouent, rien n'est commité :\n" + (r.stdout + r.stderr).strip())


# --- Orchestration ----------------------------------------------------------

def process(root: Path, downloads: Path, since_h: float, dry_run: bool, push: bool, run_tests: bool = True) -> int:
    s4_dir, polar_dir = root / "input" / "data" / "s4", root / "input" / "data" / "polar"
    data_dir = root / "data"

    other = outside_data(dirty_paths(root), "data")
    if other and dry_run:
        print("! Autres modifications git (une vraie exécution s'arrêterait) : " + ", ".join(other))
    elif other:
        raise ProcessError("L'arbre git contient d'autres modifications, commit ou range-les d'abord :\n  " + "\n  ".join(other))

    moved = collect(downloads, s4_dir, polar_dir, since_h, dry_run)
    if bool(moved["s4"]) != bool(moved["polar"]):
        missing = "Polar" if moved["s4"] else "WaterRower (S4)"
        print(f"! Il manque l'export {missing} : la séance ne sera fusionnée qu'une fois les deux présents.")
    if dry_run:
        print("Simulation : rien n'a été déplacé, fusionné ni poussé.")
        return 0

    before = load_index(data_dir)
    rc = m.main(["--auto", "--s4-dir", str(s4_dir), "--polar-dir", str(polar_dir), "--out", str(data_dir)])
    if rc != 0:
        raise ProcessError("La fusion a échoué, rien n'est commité.")

    if not git(root, "status", "--porcelain", "data").strip():
        print("Rien de nouveau : data/ est déjà à jour.")
        return 0

    after = load_index(data_dir)
    new = [after[i] for i in after if i not in before]
    for e in new:
        print(f"★ Nouvelle séance : {describe(e)}" + ("  (FC partielle !)" if e.get("overlapWarning") else ""))
    if run_tests and new:
        run_pytest(root)

    if len(new) == 1:
        msg = f"Nouvelle séance {new[0]['date'][:10]}"
    elif new:
        msg = f"Nouvelles séances {', '.join(e['date'][:10] for e in new)}"
    else:
        msg = "Mise à jour des données"
    git(root, "add", "data")
    git(root, "commit", "-m", msg)
    print(f"✓ Commit : {msg}")
    if push:
        git(root, "push")
        print(f"✓ Poussé. Le site sera à jour dans ~1 min : {SITE_URL}")
    else:
        print("Commit local uniquement (--no-push).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--downloads", type=Path, default=DEFAULT_DOWNLOADS, help="dossier des exports (défaut : ~/Downloads)")
    ap.add_argument("--since", type=float, default=DEFAULT_SINCE_H, help="ne prend que les fichiers des N dernières heures (défaut : 24)")
    ap.add_argument("--dry-run", action="store_true", help="montre ce qui serait ramassé, sans rien modifier")
    ap.add_argument("--no-push", action="store_true", help="commit local, sans push")
    args = ap.parse_args(argv)
    try:
        return process(m.ROOT, args.downloads, args.since, args.dry_run, push=not args.no_push)
    except ProcessError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
