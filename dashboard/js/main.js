// Point d'entrée : charge le catalogue puis orchestre les modules d'affichage
import { loadIndex } from './data.js';
import { state, showError } from './state.js';
import { initTheme } from './theme.js';
import { renderKpis } from './kpis.js';
import { renderHistory } from './history.js';
import { renderDetail, updateNav } from './detail.js';
import * as charts from './charts.js';

// Tableau + flèches (l'ordre des lignes change avec le tri)
function refreshHistory() {
  renderHistory({ onSelect: select, onSort: refreshHistory });
  if (state.selectedId) updateNav(select);
}

function select(id, scroll = true) {
  state.selectedId = id;
  refreshHistory();
  return renderDetail(id, scroll);
}

initTheme(() => {
  charts.progression(state.sessions);
  if (state.selectedId) select(state.selectedId);
});

try {
  state.sessions = (await loadIndex()).sessions;
  if (!state.sessions.length) throw new Error('Aucune séance dans data/index.json. Lance scripts/merge_tcx.py.');
  renderKpis();
  refreshHistory();
  charts.progression(state.sessions);
  select(state.sessions.at(-1).id);
} catch (e) { showError(e); }
