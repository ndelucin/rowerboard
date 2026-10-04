#!/usr/bin/env python3
"""Fusionne un export TCX WaterRower S4 et un export TCX Polar (FC) en un JSON de séance.

Voir docs/schema.md pour le format de sortie.
"""
from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
HR_TOLERANCE_S = 15.0
AUTO_PAIR_WINDOW_S = 300.0
ZONE_LIMITS = (0.6, 0.7, 0.8, 0.9, 1.01)  # fractions de FC max (Z1..Z5)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_S4_DIR = ROOT / "input" / "data" / "s4"
DEFAULT_POLAR_DIR = ROOT / "input" / "data" / "polar"
DEFAULT_OUT_DIR = ROOT / "data"


# --- Parsing TCX -----------------------------------------------------------

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find(el: ET.Element, name: str) -> ET.Element | None:
    """Premier descendant dont le nom local vaut `name` (indépendant des namespaces)."""
    for e in el.iter():
        if _local(e.tag) == name:
            return e
    return None


def _num(el: ET.Element | None) -> float | None:
    if el is None or el.text is None:
        return None
    try:
        v = float(el.text)
    except ValueError:
        return None
    return v if v == v else None  # écarte NaN


def _val(el: ET.Element, name: str) -> float | None:
    return _num(_find(el, name))


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.strip().replace("Z", "+00:00")).astimezone(timezone.utc)


def _load_lap(path: Path, label: str) -> ET.Element:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        raise ValueError(f"Fichier {label} illisible ({path.name}) : {e}") from e
    lap = _find(root, "Lap")
    if lap is None:
        raise ValueError(f"Aucune séance trouvée dans le fichier {label} ({path.name})")
    return lap


def parse_s4(path: Path) -> dict:
    lap = _load_lap(path, "S4")
    points = []
    for tp in (e for e in lap.iter() if _local(e.tag) == "Trackpoint"):
        t = _find(tp, "Time")
        if t is None or not t.text:
            continue
        points.append({
            "t": parse_time(t.text),
            "distance": _val(tp, "DistanceMeters"),
            "cadence": _val(tp, "Cadence"),
            "watts": _val(tp, "Watts"),
            "strokeRate": _val(tp, "StrokeRate"),
        })
    if not points:
        raise ValueError(f"Aucun point de mesure dans le fichier S4 ({path.name})")
    return {
        "total_time": _val(lap, "TotalTimeSeconds"),
        "total_distance": _val(lap, "DistanceMeters"),
        "calories": _val(lap, "Calories"),
        "points": points,
    }


def parse_polar(path: Path) -> dict:
    lap = _load_lap(path, "Polar")
    points = []
    for tp in (e for e in lap.iter() if _local(e.tag) == "Trackpoint"):
        t = _find(tp, "Time")
        hr_outer = _find(tp, "HeartRateBpm")
        hr = _val(hr_outer, "Value") if hr_outer is not None else None
        if t is None or not t.text or hr is None:
            continue
        points.append((parse_time(t.text), hr))
    if not points:
        raise ValueError(f"Aucune fréquence cardiaque dans le fichier Polar ({path.name})")
    points.sort(key=lambda p: p[0])
    return {"calories": _val(lap, "Calories"), "points": points}


# --- Fusion ----------------------------------------------------------------

def nearest_hr(polar_points, polar_ts, t: datetime, tolerance_s: float = HR_TOLERANCE_S):
    """FC du point Polar le plus proche de `t`, ou None si l'écart dépasse la tolérance."""
    ts = t.timestamp()
    i = bisect.bisect_left(polar_ts, ts)
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(polar_ts):
            d = abs(polar_ts[j] - ts)
            if best is None or d < best[0]:
                best = (d, polar_points[j][1])
    return best[1] if best and best[0] <= tolerance_s else None


def _avg(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _round(v, n=1):
    return None if v is None else round(v, n)


def compute_session(s4: dict, polar: dict, fcmax: float) -> dict:
    polar_pts = polar["points"]
    polar_ts = [p[0].timestamp() for p in polar_pts]
    start = s4["points"][0]["t"]

    series = []
    for p in s4["points"]:
        series.append({
            "t": round((p["t"] - start).total_seconds(), 1),
            "distance": p["distance"],
            "cadence": p["cadence"],
            "watts": p["watts"],
            "strokeRate": p["strokeRate"],
            "hr": nearest_hr(polar_pts, polar_ts, p["t"]),
        })

    watts = [s["watts"] for s in series if s["watts"] is not None]
    hrs = [s["hr"] for s in series if s["hr"] is not None]
    duration = s4["total_time"]
    distance = s4["total_distance"]
    avg_watts = _avg(watts)
    avg_hr = _avg(hrs)

    zone_pct = None
    if hrs:
        bounds = [f * fcmax for f in ZONE_LIMITS]
        counts = [0] * len(bounds)
        for h in hrs:
            for i, b in enumerate(bounds):
                if h < b:
                    counts[i] += 1
                    break
        zone_pct = [round(c / len(hrs) * 100) for c in counts]

    end = s4["points"][-1]["t"]
    overlap = min(end, polar_pts[-1][0]) - max(start, polar_pts[0][0])
    overlap_warning = overlap.total_seconds() < (duration or 0) * 0.5

    date = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "version": SCHEMA_VERSION,
        "id": date,
        "date": date,
        "fcmaxAtSave": fcmax,
        "summary": {
            "duration": duration,
            "distance": distance,
            "calories": s4["calories"],
            "caloriesPolar": polar["calories"],
            "avgWatts": _round(avg_watts, 2),
            "maxWatts": max(watts) if watts else None,
            "avgCadence": _round(_avg([s["cadence"] for s in series]), 2),
            "avgHr": _round(avg_hr, 2),
            "maxHr": max(hrs) if hrs else None,
            "avgPace500": _round(duration / distance * 500, 2) if distance and duration else None,
            "efficiency": _round(avg_watts / avg_hr, 4) if avg_watts and avg_hr else None,
            "zonePct": zone_pct,
        },
        "series": series,
        "overlapWarning": overlap_warning,
    }


# --- Sorties ---------------------------------------------------------------

def session_filename(session: dict) -> str:
    return re.sub(r"[^0-9TZ-]", "", session["id"]) + ".json"


def write_session(session: dict, out_dir: Path) -> Path:
    """Écrit data/sessions/<id>.json et met à jour data/index.json (idempotent)."""
    sessions_dir = out_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    fname = session_filename(session)
    (sessions_dir / fname).write_text(
        json.dumps(session, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    index_path = out_dir / "index.json"
    entries = []
    if index_path.exists():
        entries = json.loads(index_path.read_text(encoding="utf-8")).get("sessions", [])
    entries = [e for e in entries if e["id"] != session["id"]]
    entries.append({
        "id": session["id"], "date": session["date"], "file": f"sessions/{fname}",
        "fcmaxAtSave": session["fcmaxAtSave"], "overlapWarning": session["overlapWarning"],
        **session["summary"],
    })
    entries.sort(key=lambda e: e["date"])
    index_path.write_text(
        json.dumps({"version": SCHEMA_VERSION, "sessions": entries}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    return sessions_dir / fname


def _start_of(path: Path) -> datetime:
    lap = _load_lap(path, "TCX")
    return parse_time(lap.attrib["StartTime"])


def _safe_start(path: Path):
    """Heure de début, ou None (avec un message) si le fichier est inexploitable : il est alors sauté."""
    try:
        return _start_of(path)
    except (ValueError, KeyError, OSError, ET.ParseError) as e:
        print(f"! Fichier ignoré ({path.name}) : {e!r}", file=sys.stderr)
        return None


def auto_pairs(s4_dir: Path, polar_dir: Path, window_s: float = AUTO_PAIR_WINDOW_S):
    """Apparie chaque fichier S4 au fichier Polar de début le plus proche (dans la fenêtre)."""
    polars = [(p, t) for p in sorted(polar_dir.glob("*.[tT][cC][xX]")) if (t := _safe_start(p))]
    pairs, used = [], set()
    for s4 in sorted(s4_dir.glob("*.[tT][cC][xX]")):
        t0 = _safe_start(s4)
        if t0 is None:
            continue
        cands = [(abs((t - t0).total_seconds()), p) for p, t in polars if p not in used]
        cands = [c for c in cands if c[0] <= window_s]
        if not cands:
            print(f"! Pas de fichier Polar pour {s4.name}", file=sys.stderr)
            continue
        _, best = min(cands, key=lambda c: c[0])
        used.add(best)
        pairs.append((s4, best))
    return pairs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--s4", type=Path, help="fichier TCX WaterRower S4")
    ap.add_argument("--polar", type=Path, help="fichier TCX Polar")
    ap.add_argument("--auto", action="store_true", help="apparie tous les fichiers des dossiers d'entrée")
    ap.add_argument("--s4-dir", type=Path, default=DEFAULT_S4_DIR)
    ap.add_argument("--polar-dir", type=Path, default=DEFAULT_POLAR_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="dossier de sortie (défaut : data/)")
    ap.add_argument("--fcmax", type=float, default=180, help="FC max pour les zones (défaut : 180)")
    args = ap.parse_args(argv)

    if args.auto:
        pairs = auto_pairs(args.s4_dir, args.polar_dir)
    elif args.s4 and args.polar:
        pairs = [(args.s4, args.polar)]
    else:
        ap.error("indiquer --s4 et --polar, ou --auto")

    rc = 0
    for s4_path, polar_path in pairs:
        try:
            session = compute_session(parse_s4(s4_path), parse_polar(polar_path), args.fcmax)
        except ValueError as e:
            print(f"✗ {e}", file=sys.stderr)
            rc = 1  # on continue : une paire fautive ne doit pas bloquer les suivantes
            continue
        out = write_session(session, args.out)
        warn = " (chevauchement FC insuffisant !)" if session["overlapWarning"] else ""
        print(f"✓ {s4_path.name} + {polar_path.name} → {out}{warn}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
