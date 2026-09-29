import { $ } from './state.js';

const applyTheme = t => t ? document.documentElement.setAttribute('data-theme', t) : document.documentElement.removeAttribute('data-theme');

// Applique le thème mémorisé puis gère le bouton ; `onChange` redessine les graphiques (leurs couleurs viennent des variables CSS)
export function initTheme(onChange) {
  try { applyTheme(localStorage.getItem('theme')); } catch {}
  $('themeBtn').onclick = () => {
    const dark = document.documentElement.getAttribute('data-theme') === 'dark' ||
      (!document.documentElement.hasAttribute('data-theme') && matchMedia('(prefers-color-scheme: dark)').matches);
    const next = dark ? 'light' : 'dark';
    applyTheme(next);
    try { localStorage.setItem('theme', next); } catch {}
    onChange();
  };
}
