# Rowerboard

Fusionne les exports TCX WaterRower S4 + Polar (FC) en JSON, affichés par un dashboard statique sur GitHub Pages. Réponses et commentaires en français.

- `scripts/merge_tcx.py` : CLI de fusion (Python 3.9+, stdlib). `python scripts/merge_tcx.py --auto` lit `input/data/{s4,polar}` et écrit `data/`.
- `data/` : sorties JSON poussées sur GitHub. `input/` : sources brutes, gitignorées (contient un prototype `input/proto/rameur.html`, référence fonctionnelle).
- `docs/schema.md` : contrat JSON, à mettre à jour avec tout changement de format.
- `dashboard/` : site statique sans build (HTML + modules ES + Chart.js via CDN). `python3 scripts/build_site.py --serve` assemble `_site/` (dashboard + data) et le sert sur :8000 ; le workflow `.github/workflows/pages.yml` déploie le même `_site/` sur GitHub Pages.
- Tests : `.venv/bin/pytest scripts` (venv : `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`).
