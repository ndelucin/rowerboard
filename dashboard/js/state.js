// État partagé de la page + petits utilitaires DOM
export const $ = id => document.getElementById(id);

export const state = {
  sessions: [],       // catalogue (data/index.json), par date croissante
  sortKey: 'date',    // colonne de tri de l'historique
  sortDir: -1,        // -1 = décroissant
  selectedId: null,   // séance affichée dans le détail
};

// Séances dans l'ordre d'affichage du tableau (tri courant)
export const sortedRows = () => [...state.sessions].sort((a, b) => {
  const x = a[state.sortKey], y = b[state.sortKey];
  return (x < y ? -1 : x > y ? 1 : 0) * state.sortDir;
});

export function showError(e) {
  const box = $('msg');
  box.textContent = e.message || String(e);
  box.hidden = false;
}
