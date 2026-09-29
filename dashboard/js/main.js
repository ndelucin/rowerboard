import { loadIndex, loadSession } from './data.js';
import { dur, pace, num, date, dateTime } from './format.js';
import * as charts from './charts.js';

const $ = id => document.getElementById(id);
let sessions = [];
let sortKey = 'date', sortDir = -1, selectedId = null;

const COLUMNS = [
  ['date', 'Date', s => dateTime(s.date)],
  ['duration', 'Durée', s => dur(s.duration)],
  ['distance', 'Distance', s => num(s.distance) + ' m'],
  ['avgPace500', '/500 m', s => pace(s.avgPace500)],
  ['avgWatts', 'Watts', s => num(s.avgWatts)],
  ['avgHr', 'FC moy.', s => num(s.avgHr)],
  ['efficiency', 'W/bpm', s => num(s.efficiency, 2)],
];

// --- thème ---
const applyTheme = t => t ? document.documentElement.setAttribute('data-theme', t) : document.documentElement.removeAttribute('data-theme');
try { applyTheme(localStorage.getItem('theme')); } catch {}
$('themeBtn').onclick = () => {
  const dark = document.documentElement.getAttribute('data-theme') === 'dark' ||
    (!document.documentElement.hasAttribute('data-theme') && matchMedia('(prefers-color-scheme: dark)').matches);
  const next = dark ? 'light' : 'dark';
  applyTheme(next);
  try { localStorage.setItem('theme', next); } catch {}
  render();
};

function showError(e) {
  const box = $('msg');
  box.textContent = e.message || String(e);
  box.hidden = false;
}

// --- KPIs : totaux + delta dernière séance vs précédente ---
function renderKpis() {
  const last = sessions.at(-1), prev = sessions.at(-2);
  const totalDist = sessions.reduce((a, s) => a + (s.distance || 0), 0);
  const totalTime = sessions.reduce((a, s) => a + (s.duration || 0), 0);
  const delta = (key, lowerIsBetter, fmt) => {
    if (!prev || last[key] == null || prev[key] == null) return '';
    const d = last[key] - prev[key];
    if (!d) return '';
    const good = lowerIsBetter ? d < 0 : d > 0;
    return `<div class="d ${good ? 'good' : 'bad'}">${d > 0 ? '▲' : '▼'} ${fmt(Math.abs(d))} vs précédente</div>`;
  };
  const kpi = (l, v, d = '') => `<div class="kpi"><div class="l">${l}</div><div class="v">${v}</div>${d}</div>`;
  $('kpis').innerHTML =
    kpi('Séances', sessions.length, `<div class="d" style="color:var(--muted)">${num(totalDist / 1000, 1)} km · ${dur(totalTime)}</div>`) +
    kpi('Dernière allure /500 m', pace(last.avgPace500), delta('avgPace500', true, v => dur(v))) +
    kpi('Dernière puissance', num(last.avgWatts) + ' W', delta('avgWatts', false, v => num(v) + ' W')) +
    kpi('Dernière FC moyenne', num(last.avgHr) + ' bpm', delta('avgHr', true, v => num(v) + ' bpm')) +
    kpi('Efficacité', num(last.efficiency, 2), delta('efficiency', false, v => num(v, 2)));
  $('subtitle').textContent = `${sessions.length} séances · du ${date(sessions[0].date)} au ${date(last.date)}`;
}

function renderHistory() {
  const rows = [...sessions].sort((a, b) => {
    const x = a[sortKey], y = b[sortKey];
    return (x < y ? -1 : x > y ? 1 : 0) * sortDir;
  });
  $('history').innerHTML =
    `<thead><tr>${COLUMNS.map(([k, l]) => `<th data-k="${k}">${l}${k === sortKey ? (sortDir > 0 ? ' ↑' : ' ↓') : ''}</th>`).join('')}</tr></thead>` +
    `<tbody>${rows.map(s => `<tr data-id="${s.id}" class="${s.id === selectedId ? 'sel' : ''}">${COLUMNS.map(([, , f]) => `<td>${f(s)}</td>`).join('')}</tr>`).join('')}</tbody>`;
  $('history').querySelectorAll('th').forEach(th => th.onclick = () => {
    sortDir = th.dataset.k === sortKey ? -sortDir : -1;
    sortKey = th.dataset.k;
    renderHistory();
  });
  $('history').querySelectorAll('tbody tr').forEach(tr => tr.onclick = () => select(tr.dataset.id));
}

const ZONES = [['Z1 · récup.', '--z1'], ['Z2 · endurance', '--z2'], ['Z3 · tempo', '--z3'], ['Z4 · seuil', '--z4'], ['Z5 · max', '--z5']];

async function select(id) {
  selectedId = id;
  renderHistory();
  const entry = sessions.find(s => s.id === id);
  try {
    const session = await loadSession(entry);
    if (selectedId !== id) return; // une autre séance a été choisie entre-temps
    const sm = session.summary;
    $('detail').hidden = false;
    $('detailTitle').textContent = 'Séance du ' + dateTime(session.date);
    $('detailWarn').hidden = !session.overlapWarning;
    const stat = (l, v) => `<div class="stat"><div class="v">${v}</div><div class="l">${l}</div></div>`;
    $('detailStats').innerHTML = stat('Durée', dur(sm.duration)) + stat('Distance', num(sm.distance) + ' m') +
      stat('Allure /500 m', pace(sm.avgPace500)) + stat('Puissance moy.', num(sm.avgWatts) + ' W') + stat('Puissance max', num(sm.maxWatts) + ' W') +
      stat('Cadence moy.', num(sm.avgCadence, 1)) + stat('FC moy. / max', `${num(sm.avgHr)} / ${num(sm.maxHr)}`) + stat('Calories', num(sm.calories));
    $('zones').innerHTML = sm.zonePct
      ? ZONES.map(([l, c], i) => `<div class="zone"><span>${l}</span><span class="bar"><i style="width:${sm.zonePct[i]}%;background:var(${c})"></i></span><span>${sm.zonePct[i]} %</span></div>`).join('')
      : '<span class="sub">Pas de données de FC.</span>';
    charts.detail(session);
    if (!matchMedia('(min-width: 900px)').matches) $('detail').scrollIntoView({ behavior: 'smooth' });
  } catch (e) { showError(e); }
}

function render() {
  charts.progression(sessions);
  if (selectedId) select(selectedId);
}

try {
  sessions = (await loadIndex()).sessions;
  if (!sessions.length) throw new Error('Aucune séance dans data/index.json. Lance scripts/merge_tcx.py.');
  renderKpis();
  renderHistory();
  charts.progression(sessions);
  select(sessions.at(-1).id);
} catch (e) { showError(e); }
