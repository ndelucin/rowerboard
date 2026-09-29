# Rowerboard

Fusionne les exports TCX WaterRower S4 + Polar (FC) en JSON, affichés par un dashboard statique sur GitHub Pages. Réponses et commentaires en français.

- `scripts/merge_tcx.py` : CLI de fusion (Python 3.9+, stdlib). `python scripts/merge_tcx.py --auto` lit `input/data/{s4,polar}` et écrit `data/`.
- `data/` : sorties JSON poussées sur GitHub. `input/` : sources brutes, gitignorées.
- `docs/schema.md` : contrat JSON, à mettre à jour avec tout changement de format.
- `dashboard/` : site statique sans build (HTML + modules ES + Chart.js hébergé dans `dashboard/vendor/`, police dans `dashboard/fonts/`). Le workflow `.github/workflows/pages.yml` copie `dashboard/` et `data/` dans `_site/` puis le publie sur GitHub Pages. Test local : reproduire ces `cp` puis `cd _site && python3 -m http.server 8000`.
- Tests : `.venv/bin/pytest scripts` (venv : `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`).
