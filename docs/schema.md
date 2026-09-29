# Format des données (contrat script ↔ dashboard)

Produit par `scripts/merge_tcx.py`, lu par `dashboard/`. Toutes les durées sont en secondes, distances en mètres, dates en UTC (ISO 8601).

## `data/index.json`
```json
{ "version": 1, "sessions": [ { "id", "date", "file", "fcmaxAtSave", "overlapWarning", ...summary } ] }
```
Trié par date croissante. `file` est relatif à `data/`.

## `data/sessions/<id>.json`
```json
{
  "version": 1,
  "id": "2026-09-15T18:07:17Z",
  "date": "2026-09-15T18:07:17Z",
  "fcmaxAtSave": 180,
  "summary": {
    "duration", "distance", "calories", "caloriesPolar",
    "avgWatts", "maxWatts", "avgCadence", "avgHr", "maxHr",
    "avgPace500",   // s / 500 m
    "efficiency",   // watts moyens / FC moyenne
    "zonePct"       // [Z1..Z5] en %, bornes 60/70/80/90 % de fcmaxAtSave ; null si pas de FC
  },
  "series": [ { "t": 0.0, "distance", "cadence", "watts", "strokeRate", "hr" } ],
  "overlapWarning": false
}
```
- `series` : un point par mesure S4 (~3-4 s), `t` = secondes depuis le début de la séance S4.
- `hr` : point Polar le plus proche à ±15 s, sinon `null`.
- Une valeur absente ou invalide est `null`.

## Chiffrement (prévu, non implémenté)
`version` permettra une enveloppe `{ version, salt, iv, ciphertext }` (AES-GCM, clé PBKDF2) à la place du JSON clair.
