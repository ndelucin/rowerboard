import { $, state } from './state.js';
import { dur, pace, to2000, hhmm, num, date } from './format.js';

// --- KPIs : totaux + delta dernière séance vs précédente ---
export function renderKpis() {
  const { sessions } = state;
  const last = sessions.at(-1), prev = sessions.at(-2);
  const totalDist = sessions.reduce((a, s) => a + (s.distance || 0), 0);
  const totalTime = sessions.reduce((a, s) => a + (s.duration || 0), 0);
  const pace2000 = s => to2000(s.avgPace500);

  // Jours calendaires écoulés depuis la dernière séance (à minuit local, pour éviter les décalages d'heure)
  const midnight = d => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const days = Math.round((midnight(new Date()) - midnight(new Date(last.date))) / 86400000);
  const since = days <= 0 ? "aujourd'hui" : days === 1 ? 'hier' : `il y a ${days} jours`;

  // Écart entre la dernière séance et la précédente ; `get` extrait la valeur comparée
  const delta = (get, lowerIsBetter, fmt) => {
    if (!prev || get(last) == null || get(prev) == null) return '';
    const d = get(last) - get(prev);
    if (!d) return '';
    const good = lowerIsBetter ? d < 0 : d > 0;
    return `<div class="d ${good ? 'good' : 'bad'}">${d > 0 ? '▲' : '▼'} ${fmt(Math.abs(d))} vs précédente</div>`;
  };
  const kpi = (l, v, d = '', cls = '') => `<div class="kpi ${cls}"><div class="l">${l}</div><div class="v">${v}</div>${d}</div>`;
  $('kpis').innerHTML =
    kpi('Cumul', `<div>${sessions.length} séances</div><div>${hhmm(totalTime)}</div><div>${num(totalDist / 1000, 2)} km</div>`, '', 'cumul') +
    kpi('Dernière allure /2000 m', pace(pace2000(last)), delta(pace2000, true, dur)) +
    kpi('Dernière FC moyenne', num(last.avgHr) + ' bpm', delta(s => s.avgHr, true, v => num(v) + ' bpm')) +
    kpi('Durée dernière séance', dur(last.duration), delta(s => s.duration, false, dur)) +
    kpi('Dernière efficience (W/bpm)', num(last.efficiency, 2), delta(s => s.efficiency, false, v => num(v, 2)));
  $('subtitle').textContent = `${sessions.length} séances · du ${date(sessions[0].date)} au ${date(last.date)} - Dernière séance : ${since}`;
}
