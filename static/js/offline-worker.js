/* Cache only the public, self-contained offline page; never account/API data. */
const OFFLINE_CACHE = 'linkify-offline-v1';
const OFFLINE_URL = '/offline/';
self.addEventListener('install', event => {
    event.waitUntil((async () => {
        const cache = await caches.open(OFFLINE_CACHE);
        await cache.add(new Request(OFFLINE_URL, {cache: 'reload'}));
        await self.skipWaiting();
    })());
});
self.addEventListener('activate', event => {
    event.waitUntil((async () => {
        for (const name of await caches.keys()) {
            if (name.startsWith('linkify-offline-') && name !== OFFLINE_CACHE) await caches.delete(name);
        }
        await self.clients.claim();
    })());
});
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    if (event.request.mode !== 'navigate' || event.request.method !== 'GET' ||
        url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
    event.respondWith((async () => {
        try {
            return await fetch(event.request);
        } catch (error) {
            const cache = await caches.open(OFFLINE_CACHE);
            return await cache.match(OFFLINE_URL) || new Response('Connection unavailable. Reconnect and retry.', {
                status: 503, headers: {'Content-Type': 'text/plain; charset=utf-8'},
            });
        }
    })());
});
