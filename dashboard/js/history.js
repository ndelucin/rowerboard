import { $, state, sortedRows } from './state.js';
import { dur, pace, to2000, num, dateTime } from './format.js';

const COLUMNS = [
  ['date', 'Date', s => dateTime(s.date)],
  ['duration', 'Durée', s => dur(s.duration)],
  ['distance', 'Distance', s => num(s.distance) + ' m'],
  ['avgPace500', '/2000 m', s => pace(to2000(s.avgPace500))],
  ['avgWatts', 'Watts', s => num(s.avgWatts)],
  ['avgHr', 'FC moy.', s => num(s.avgHr)],
  ['efficiency', 'W/bpm', s => num(s.efficiency, 2)],
];

// Tableau triable ; `onSelect(id)` au clic sur une ligne, `onSort()` après un changement de tri
export function renderHistory({ onSelect, onSort }) {
  const { sortKey, sortDir, selectedId } = state;
  $('history').innerHTML =
    `<thead><tr>${COLUMNS.map(([k, l]) => `<th data-k="${k}">${l}${k === sortKey ? (sortDir > 0 ? ' ↑' : ' ↓') : ''}</th>`).join('')}</tr></thead>` +
    `<tbody>${sortedRows().map(s => `<tr data-id="${s.id}" class="${s.id === selectedId ? 'sel' : ''}">${COLUMNS.map(([, , f]) => `<td>${f(s)}</td>`).join('')}</tr>`).join('')}</tbody>`;
  $('history').querySelectorAll('th').forEach(th => th.onclick = () => {
    state.sortDir = th.dataset.k === state.sortKey ? -state.sortDir : -1;
    state.sortKey = th.dataset.k;
    onSort();
  });
  $('history').querySelectorAll('tbody tr').forEach(tr => tr.onclick = () => onSelect(tr.dataset.id));
}
