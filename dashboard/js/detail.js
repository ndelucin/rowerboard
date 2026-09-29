import { $, state, sortedRows, showError } from './state.js';
import { loadSession } from './data.js';
import { dur, pace, to2000, num, dateTime } from './format.js';
import * as charts from './charts.js';

const ZONES = [['Z1 · récup.', '--z1'], ['Z2 · endurance', '--z2'], ['Z3 · tempo', '--z3'], ['Z4 · seuil', '--z4'], ['Z5 · max', '--z5']];

// Flèches haut / bas : ligne voisine du tableau, active seulement si elle existe
export function updateNav(onSelect) {
  const rows = sortedRows(), idx = rows.findIndex(s => s.id === state.selectedId);
  const set = (btn, target) => {
    btn.disabled = !target;
    btn.onclick = target ? () => onSelect(target.id, false) : null;
  };
  set($('prevBtn'), rows[idx - 1]);
  set($('nextBtn'), rows[idx + 1]);
}

// Panneau « Détails de la séance » (statistiques, zones de FC, graphiques)
export async function renderDetail(id, scroll = true) {
  const entry = state.sessions.find(s => s.id === id);
  try {
    const session = await loadSession(entry);
    if (state.selectedId !== id) return; // une autre séance a été choisie entre-temps
    const sm = session.summary;
    $('detail').hidden = false;
    $('detailTitle').textContent = 'Détails de la séance du ' + dateTime(session.date);
    $('detailWarn').hidden = !session.overlapWarning;
    const stat = (l, v) => `<div class="stat"><div class="v">${v}</div><div class="l">${l}</div></div>`;
    $('detailStats').innerHTML = stat('Durée', dur(sm.duration)) + stat('Distance', num(sm.distance) + ' m') +
      stat('Allure /2000 m', pace(to2000(sm.avgPace500))) + stat('Puissance moy.', num(sm.avgWatts) + ' W') + stat('Puissance max', num(sm.maxWatts) + ' W') +
      stat('Cadence moy.', num(sm.avgCadence, 1)) + stat('FC moy. / max', `${num(sm.avgHr)} / ${num(sm.maxHr)}`) + stat('Calories', num(sm.calories));
    $('zones').innerHTML = sm.zonePct
      ? ZONES.map(([l, c], i) => `<div class="zone"><span>${l}</span><span class="bar"><i style="width:${sm.zonePct[i]}%;background:var(${c})"></i></span><span>${sm.zonePct[i]} %</span></div>`).join('')
      : '<span class="sub">Pas de données de FC.</span>';
    charts.detail(session);
    if (scroll && !matchMedia('(min-width: 900px)').matches) $('detail').scrollIntoView({ behavior: 'smooth' });
  } catch (e) { showError(e); }
}
