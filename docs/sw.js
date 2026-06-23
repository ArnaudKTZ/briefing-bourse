const CACHE = 'agent-bourse-v3';
const RAW   = 'https://raw.githubusercontent.com/ArnaudKTZ/briefing-bourse/main';

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

let derniereBriefingVu  = null;
let derniereAlerteVue   = null;

async function verifierBriefing() {
  try {
    const r = await fetch(`${RAW}/dernier_briefing.json?t=${Date.now()}`);
    if (!r.ok) return;
    const d = await r.json();
    const cle = d.date + '_' + d.heure;
    if (cle === derniereBriefingVu) return;
    derniereBriefingVu = cle;
    const cacStr = d.cac_cours ? ` · CAC ${Math.round(d.cac_cours).toLocaleString('fr')}` : '';
    const varStr = d.cac_var !== undefined ? ` (${d.cac_var > 0 ? '+' : ''}${parseFloat(d.cac_var).toFixed(2)}%)` : '';
    self.registration.showNotification(`Briefing Bourse — ${d.date}`, {
      body: `Votre briefing du matin est prêt${cacStr}${varStr}`,
      icon: 'icon-192.png',
      badge: 'icon-192.png',
      tag: 'briefing-matin',
      renotify: true,
      vibrate: [100, 50, 100],
      data: { url: self.registration.scope },
    });
  } catch(e) {}
}

async function verifierAlertes() {
  try {
    const r = await fetch(`${RAW}/alertes_envoyees.json?t=${Date.now()}`);
    if (!r.ok) return;
    const data = await r.json();
    const alertes = Object.entries(data);
    if (alertes.length === 0) return;
    const derniere = alertes.sort((a, b) => {
      const da = (a[1].date || '') + (a[1].heure || '');
      const db = (b[1].date || '') + (b[1].heure || '');
      return db.localeCompare(da);
    })[0];
    const cle = derniere[0];
    if (cle === derniereAlerteVue) return;
    derniereAlerteVue = cle;
    const al = derniere[1];
    self.registration.showNotification('Agent Bourse — Signal fort !', {
      body: `${cle.split('_')[0]} · Score ${al.score || ''}${al.signal ? ' · ' + al.signal : ''}`,
      icon: 'icon-192.png',
      badge: 'icon-192.png',
      tag: 'alerte-signal',
      renotify: true,
      vibrate: [200, 100, 200, 100, 200],
      data: { url: self.registration.scope },
    });
  } catch(e) {}
}

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = e.notification.data?.url || self.registration.scope;
  e.waitUntil(clients.openWindow(url));
});

self.addEventListener('message', e => {
  if (e.data === 'START_POLLING') {
    verifierBriefing();
    verifierAlertes();
    setInterval(verifierBriefing,  5 * 60 * 1000);
    setInterval(verifierAlertes,   5 * 60 * 1000);
  }
});
