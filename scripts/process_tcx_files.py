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
    """Heure de début d'un TCX (lue dans le fichier), ou None s'il est illisible."""
    try:
        return m._start_of(path)
    except (ValueError, KeyError, OSError):
        return None


def _starts(directory: Path) -> set:
    """Heures de début des TCX déjà rangés (identifie une séance quel que soit le nom du fichier)."""
    return {t for t in (_start(p) for p in directory.glob("*.[tT][cC][xX]")) if t} if directory.is_dir() else set()


def collect(downloads: Path, s4_dir: Path, polar_dir: Path, since_h: float, dry_run: bool):
    """Déplace les TCX récents de `downloads` vers les dossiers d'entrée. Retourne {'s4': [...], 'polar': [...]}.

    Ne touche qu'aux fichiers modifiés depuis `since_h` heures. Un TCX sans heure de début lisible est
    ignoré (il ferait planter la fusion). Une séance déjà rangée (même heure de début) est laissée dans
    Downloads ; si seul le nom de fichier est déjà pris, le nouveau fichier est renommé avec son heure
    de début. En `dry_run`, on liste sans déplacer.
    """
    moved = {"s4": [], "polar": []}
    if not downloads.is_dir():
        raise ProcessError(f"Dossier introuvable : {downloads}")
    limit = time.time() - since_h * 3600
    known = {"s4": _starts(s4_dir), "polar": _starts(polar_dir)}  # heures de début déjà rangées, par type
    for p in sorted(downloads.glob("*.[tT][cC][xX]")):
        try:
            if p.stat().st_mtime < limit:
                continue
        except OSError:  # lien symbolique cassé, fichier disparu…
            continue
        kind = classify(p)
        start = _start(p) if kind else None
        if kind is None or start is None:
            print(f"! Ignoré (TCX non reconnu ou sans heure de début) : {p.name}", file=sys.stderr)
            continue
        if start in known[kind]:
            print(f"= Déjà présent (même séance), laissé dans {downloads.name}/ : {p.name}")
            continue
        dest_dir = s4_dir if kind == "s4" else polar_dir
        dest = dest_dir / p.name
        if dest.exists():  # même nom mais autre séance : on ne l'écrase pas et on ne l'ignore pas
            dest = dest_dir / f"{p.stem}_{start:%Y%m%dT%H%M%S}{p.suffix}"
        print(f"→ {kind:5} {p.name}" + (f" (renommé {dest.name})" if dest.name != p.name else ""))
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), dest)
        known[kind].add(start)
        moved[kind].append(p.name)
    return moved


# --- Git --------------------------------------------------------------------

def git(root: Path, *args: str) -> str:
    """Lance `git <args>` dans `root` et retourne sa sortie ; lève ProcessError si la commande échoue."""
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        raise ProcessError(f"git {' '.join(args)} a échoué :\n{r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def dirty_paths(root: Path) -> list[str]:
    """Fichiers modifiés ou non suivis (hors fichiers ignorés)."""
    return [l[3:] for l in git(root, "status", "--porcelain").splitlines()]


def outside_data(paths: list[str], data_rel: str) -> list[str]:
    """Parmi `paths`, ceux qui ne sont pas dans `data_rel` : seules les modifs de data/ sont attendues."""
    return [p for p in paths if not (p.strip('"') + "/").startswith(data_rel + "/")]


# --- Rapport ----------------------------------------------------------------

def load_index(data_dir: Path) -> dict:
    """Lit data/index.json et retourne {id de séance: entrée}. Vide si le fichier n'existe pas encore."""
    p = data_dir / "index.json"
    if not p.exists():
        return {}
    return {e["id"]: e for e in json.loads(p.read_text(encoding="utf-8")).get("sessions", [])}


def committed_index(root: Path) -> dict:
    """Index tel qu'il est dans le dernier commit (vide s'il n'y en a pas encore).

    Sert de référence pour savoir ce qui est « nouveau » : contrairement à l'état du disque, il reste
    juste si une exécution précédente a fusionné sans aboutir à un commit.
    """
    r = subprocess.run(["git", "show", "HEAD:data/index.json"], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    return {e["id"]: e for e in json.loads(r.stdout).get("sessions", [])}


def unpushed_count(root: Path) -> int:
    """Nombre de commits locaux pas encore poussés (0 si aucune branche distante n'est suivie)."""
    r = subprocess.run(["git", "rev-list", "--count", "@{u}..HEAD"], cwd=root, capture_output=True, text=True)
    return int(r.stdout) if r.returncode == 0 else 0


def describe(e: dict) -> str:
    """Résumé d'une séance sur une ligne : date · durée · distance · allure /2000 m."""
    d = e["date"][:10]
    pace = e.get("avgPace500")
    p2000 = f"{int(pace * 4 // 60)}:{int(pace * 4 % 60):02d}" if pace else "–"
    return f"{d[8:]}/{d[5:7]}/{d[2:4]} · {int(e['duration'] // 60)}:{int(e['duration'] % 60):02d} · {e['distance']:.0f} m · {p2000} /2000 m"


def run_pytest(root: Path) -> None:
    """Lance les tests avec le pytest du .venv ; lève ProcessError s'ils échouent (donc pas de commit)."""
    exe = root / ".venv" / "bin" / "pytest"
    if not exe.exists():
        print("! .venv absent : tests non lancés")
        return
    r = subprocess.run([str(exe), "-q", "scripts"], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        raise ProcessError("Les tests échouent, rien n'est commité :\n" + (r.stdout + r.stderr).strip())


# --- Orchestration ----------------------------------------------------------

def process(root: Path, downloads: Path, since_h: float, dry_run: bool, push: bool, run_tests: bool = True) -> int:
    """Enchaîne : vérif git propre → ramassage → fusion → rapport → tests → commit → push. Retourne le code de sortie."""
    s4_dir, polar_dir = root / "input" / "data" / "s4", root / "input" / "data" / "polar"
    data_dir = root / "data"

    # 1. Garde-fou : on ne commite que data/, donc tout autre changement git doit être réglé avant.
    other = outside_data(dirty_paths(root), "data")
    if other and dry_run:
        print("! Autres modifications git (une vraie exécution s'arrêterait) : " + ", ".join(other))
    elif other:
        raise ProcessError("L'arbre git contient d'autres modifications, commit ou range-les d'abord :\n  " + "\n  ".join(other))

    # 2. Ramassage des TCX dans Downloads ; on signale s'il manque l'un des deux exports.
    moved = collect(downloads, s4_dir, polar_dir, since_h, dry_run)
    if bool(moved["s4"]) != bool(moved["polar"]):
        missing = "Polar" if moved["s4"] else "WaterRower (S4)"
        print(f"! Il manque l'export {missing} : la séance ne sera fusionnée qu'une fois les deux présents.")
    if dry_run:
        print("Simulation : rien n'a été déplacé, fusionné ni poussé.")
        return 0

    # 3. Fusion S4 + Polar. Les séances « nouvelles » sont celles absentes du dernier commit.
    before = committed_index(root)
    rc = m.main(["--auto", "--s4-dir", str(s4_dir), "--polar-dir", str(polar_dir), "--out", str(data_dir)])
    if rc != 0:
        raise ProcessError("La fusion a échoué, rien n'est commité.")

    # 4. Si data/ n'a pas changé, il n'y a rien à commiter ; mais on rattrape un push qui avait échoué.
    if not git(root, "status", "--porcelain", "data").strip():
        print("Rien de nouveau : data/ est déjà à jour.")
        ahead = unpushed_count(root)
        if push and ahead:
            git(root, "push")
            print(f"✓ {ahead} commit(s) en attente poussé(s). Le site sera à jour dans ~1 min : {SITE_URL}")
        elif ahead:
            print(f"! {ahead} commit(s) local(aux) pas encore poussé(s).")
        return 0

    after = load_index(data_dir)
    new = [after[i] for i in after if i not in before]
    for e in new:
        print(f"★ Nouvelle séance : {describe(e)}" + ("  (FC partielle !)" if e.get("overlapWarning") else ""))
    if run_tests:  # toujours, dès que data/ a changé : même si la séance a été fusionnée par un run précédent
        run_pytest(root)

    # 5. Message de commit selon le nombre de séances ajoutées, puis commit et push (sauf --no-push).
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
    """Point d'entrée CLI : lit les options, appelle process() et affiche proprement les ProcessError."""
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
