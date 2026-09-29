import { pace, to2000, dur } from './format.js';

const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const charts = {};

function make(id, config) {
  charts[id]?.destroy();
  const muted = css('--muted'), grid = css('--grid');
  Chart.defaults.color = muted;
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  for (const s of Object.values(config.options.scales)) {
    s.grid = { color: grid, drawOnChartArea: s.position !== 'right', ...s.grid };
    s.border = { display: false };
  }
  config.options = { responsive: true, maintainAspectRatio: false, animation: false, interaction: { mode: 'index', intersect: false },
    ...config.options, plugins: { legend: { display: !!config.options.legend, labels: { boxWidth: 10 } }, ...config.options.plugins } };
  charts[id] = new Chart(document.getElementById(id), config);
}

const line = (label, data, color, extra = {}) => ({ label, data, borderColor: color, backgroundColor: color, borderWidth: 2, pointRadius: 0, tension: .25, spanGaps: false, ...extra });

// --- Progression : une valeur par séance ---
export function progression(sessions) {
  const labels = sessions.map(s => new Date(s.date).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }));
  const one = (id, key, color, opts = {}) => make(id, {
    // `get` extrait la valeur tracée (par défaut la clé du résumé de séance)
    type: 'line',
    data: { labels, datasets: [line(key, sessions.map(opts.get || (s => s[key])), color, { pointRadius: 4, pointHoverRadius: 6 })] },
    options: { scales: { x: {}, y: { reverse: !!opts.reverse, ticks: { callback: opts.fmt } } },
      plugins: { tooltip: { callbacks: { label: c => (opts.fmt ? opts.fmt(c.parsed.y) : c.parsed.y) } } } },
  });
  one('cPace', 'avgPace500', css('--c1'), { reverse: true, fmt: pace, get: s => to2000(s.avgPace500) });
  one('cWatts', 'avgWatts', css('--c3'));
  one('cHr', 'avgHr', css('--c2'));
  one('cEff', 'efficiency', css('--c4'), { fmt: v => v.toFixed(2) });
}

// Allure /2000 m sur une fenêtre glissante de ~30 s
function rollingPace(series, windowS = 30) {
  return series.map((p, i) => {
    let j = i;
    while (j > 0 && p.t - series[j].t < windowS) j--;
    const dd = p.distance - series[j].distance, dt = p.t - series[j].t;
    const v = dd > 0 && dt > 0 ? 500 * dt / dd : null;
    return v && v >= 60 && v <= 300 ? to2000(v) : null; // (filtre sur l'allure /500 m) écarte les pauses / arrêts
  });
}

// --- Détail d'une séance ---
export function detail(session) {
  const s = session.series;
  const t = s.map(p => p.t);
  const xTicks = { callback: (_, i) => dur(t[i]), maxTicksLimit: 8 };

  make('dWattsHr', {
    type: 'line',
    data: { labels: t, datasets: [
      line('Puissance (W)', s.map(p => p.watts), css('--c1'), { yAxisID: 'y' }),
      line('FC (bpm)', s.map(p => p.hr), css('--c2'), { yAxisID: 'y1' }),
    ] },
    options: { legend: true, scales: {
      x: { ticks: xTicks },
      y: { position: 'left', title: { display: true, text: 'W' }, beginAtZero: true },
      y1: { position: 'right', title: { display: true, text: 'bpm' } },
    }, plugins: { tooltip: { callbacks: { title: it => dur(t[it[0].dataIndex]) } } } },
  });
  make('dPace', {
    type: 'line',
    data: { labels: t, datasets: [line('Allure', rollingPace(s), css('--c3'))] },
    options: { scales: { x: { ticks: xTicks }, y: { reverse: true, ticks: { callback: pace } } },
      plugins: { tooltip: { callbacks: { title: it => dur(t[it[0].dataIndex]), label: c => pace(c.parsed.y) + ' /2000 m' } } } },
  });
  make('dCad', {
    type: 'line',
    data: { labels: t, datasets: [line('Cadence', s.map(p => p.cadence), css('--c4'))] },
    options: { scales: { x: { ticks: xTicks }, y: { beginAtZero: true } },
      plugins: { tooltip: { callbacks: { title: it => dur(t[it[0].dataIndex]) } } } },
  });
}
