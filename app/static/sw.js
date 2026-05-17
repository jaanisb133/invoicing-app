// V-Rēķini service worker
// Cache strategy: cache-first for /static/, network-first for HTML pages
const CACHE = 'vrekini-v1';
const STATIC_ASSETS = [
    '/static/css/style.css?v=15',
    '/static/manifest.json',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/icons/apple-touch-icon.png',
];

self.addEventListener('install', (ev) => {
    ev.waitUntil(
        caches.open(CACHE).then((c) => c.addAll(STATIC_ASSETS).catch(() => {}))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (ev) => {
    ev.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (ev) => {
    const req = ev.request;
    if (req.method !== 'GET') return;
    const url = new URL(req.url);
    if (url.origin !== location.origin) return;

    // Cache-first for static assets
    if (url.pathname.startsWith('/static/')) {
        ev.respondWith(
            caches.match(req).then((cached) => {
                if (cached) return cached;
                return fetch(req).then((resp) => {
                    if (resp.ok) {
                        const clone = resp.clone();
                        caches.open(CACHE).then((c) => c.put(req, clone));
                    }
                    return resp;
                });
            })
        );
        return;
    }

    // Network-first for everything else (HTML, API). Falls back to cached HTML if offline.
    if (req.headers.get('accept')?.includes('text/html')) {
        ev.respondWith(
            fetch(req)
                .then((resp) => {
                    if (resp.ok) {
                        const clone = resp.clone();
                        caches.open(CACHE).then((c) => c.put(req, clone));
                    }
                    return resp;
                })
                .catch(() =>
                    caches.match(req).then((cached) => cached || new Response(
                        '<!doctype html><meta charset=utf-8><title>Bezsaiste</title><body style="font-family:system-ui;padding:32px;background:#07080B;color:#FAFAFA;text-align:center"><h1>Esat bezsaistē</h1><p>Lūdzu, pārbaudiet interneta savienojumu.</p>',
                        { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
                    ))
                )
        );
    }
});
