#!/usr/bin/env python3
"""Assemble le site statique dans _site/ (dashboard/ + data/) ; --serve pour le tester en local.

Deux usages :
  - en CI : le workflow .github/workflows/pages.yml lance ce script, puis publie _site/ sur GitHub Pages ;
  - en local : `python3 scripts/build_site.py --serve` construit _site/ puis le sert sur http://localhost:8000.

Pourquoi un dossier _site/ ? Le dashboard va chercher ses données à l'adresse relative
`data/index.json`. Dans le dépôt, dashboard/ et data/ sont deux dossiers frères ; sur le site
publié, data/ doit se trouver *dans* le dossier du site. Ce script fait cette réorganisation.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import shutil
from pathlib import Path

# Racine du dépôt : ce fichier est dans scripts/, donc on remonte d'un cran.
ROOT = Path(__file__).resolve().parent.parent
# Dossier de sortie (gitignoré : c'est un produit de build, jamais commité).
SITE = ROOT / "_site"


def build() -> None:
    # Repart d'un dossier propre pour ne garder aucun fichier obsolète
    # (par exemple une séance supprimée de data/).
    if SITE.exists():
        shutil.rmtree(SITE)
    # index.html, style.css et js/ à la racine du site...
    shutil.copytree(ROOT / "dashboard", SITE)
    # ...et les JSON générés par merge_tcx.py dans _site/data/.
    # input/ n'est volontairement jamais copié : les fichiers TCX bruts restent locaux.
    shutil.copytree(ROOT / "data", SITE / "data")
    print(f"✓ site assemblé dans {SITE}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    # `--serve` seul = port 8000 ; `--serve 9000` = port 9000 ; sans l'option = pas de serveur (mode CI).
    ap.add_argument("--serve", type=int, nargs="?", const=8000, metavar="PORT")
    args = ap.parse_args()
    build()
    if args.serve:
        # Petit serveur de fichiers de la bibliothèque standard, qui imite ce que fait GitHub Pages
        # (des fichiers statiques, rien d'autre). Écoute seulement sur 127.0.0.1 : accessible
        # uniquement depuis ta machine. Il ne reconstruit pas _site/ : relance le script
        # après avoir modifié le dashboard ou les données.
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
        print(f"→ http://localhost:{args.serve}")
        http.server.ThreadingHTTPServer(("127.0.0.1", args.serve), handler).serve_forever()
