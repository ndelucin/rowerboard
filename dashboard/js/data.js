// Seul point d'accès aux données : c'est ici que se brancherait le déchiffrement (enveloppe { version, salt, iv, ciphertext }).
async function loadJson(path) {
  const res = await fetch(path, { cache: 'no-cache' });
  if (!res.ok) throw new Error(`Impossible de charger ${path} (${res.status})`);
  return res.json();
}

export const loadIndex = () => loadJson('data/index.json');

const cache = new Map();
export function loadSession(entry) {
  if (!cache.has(entry.id)) cache.set(entry.id, loadJson('data/' + entry.file));
  return cache.get(entry.id);
}
