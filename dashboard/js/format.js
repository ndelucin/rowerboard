export const dur = s => {
  if (s == null) return '–';
  s = Math.round(s);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(r).padStart(2, '0');
};
// Allure /500 m (s) → allure /2000 m (s)
export const to2000 = s => s == null ? null : s * 4;
export const pace = s => (s == null || !isFinite(s) || s <= 0) ? '–' : dur(s);
export const num = (v, d = 0) => v == null ? '–' : v.toLocaleString('fr-FR', { maximumFractionDigits: d, minimumFractionDigits: d });
export const date = iso => new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: '2-digit' });
export const dateTime = iso => date(iso) + ' ' + new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
// Durée cumulée : 7h12
export const hhmm = s => `${Math.floor(s / 3600)}h${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}`;
