const CACHE = 'agent-bourse-v2';
const REPO_RAW = 'https://raw.githubusercontent.com/ArnaudKTZ/briefing-bourse/main';

self.addEventListener('install', e => { self.skipWaiting(); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  if (e.request.url.includes('raw.githubusercontent.com')) return;
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});

// Polling alertes toutes les 5 minutes
let derniereAlerteVue = null;

async function verifierAlertes() {
  try {
    const r = await fetch(`${REPO_RAW}/alertes_envoyees.json?t=${Date.now()}`);
    if (!r.ok) return;
    const data = await r.json();
    const alertes = Object.entries(data);
    if (alertes.length === 0) return;

    // Trouver la plus récente
    const derniere = alertes.sort((a, b) => {
      const da = a[1].date + ' ' + (a[1].heure || '');
      const db = b[1].date + ' ' + (b[1].heure || '');
      return db.localeCompare(da);
    })[0];

    const cle = derniere[0];
    if (cle === derniereAlerteVue) return;
    derniereAlerteVue = cle;

    const alerte = derniere[1];
    self.registration.showNotification('Agent Bourse — Alerte !', {
      body: `${cle} · Score ${alerte.score || ''}${alerte.signal ? ' · ' + alerte.signal : ''}`,
      icon: 'icon-192.png',
      badge: 'icon-192.png',
      tag: 'alerte-bourse',
      renotify: true,
      vibrate: [200, 100, 200],
    });
  } catch(e) {}
}

self.addEventListener('message', e => {
  if (e.data === 'START_POLLING') {
    verifierAlertes();
    setInterval(verifierAlertes, 5 * 60 * 1000);
  }
});
