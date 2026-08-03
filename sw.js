/* Lexia — service worker
 *
 * Criterio: RED PRIMERO para el sistema, caché solo como red de seguridad.
 * El objetivo es que una versión nueva llegue en el próximo arranque, sin que
 * nadie tenga que hacer Ctrl+F5 ni desinstalar nada. La caché existe únicamente
 * para que, si la conexión falla, no aparezca la pantalla de error del navegador.
 *
 * Al publicar una versión nueva del sistema conviene subir CACHE_VERSION: eso
 * descarta la caché anterior de una.
 */

const CACHE_VERSION = 'lexia-v1';
const ESENCIALES = [
  './',
  './manifest.webmanifest',
  './icono-192.png',
  './icono-512.png',
  './apple-touch-icon.png',
  './favicon.png'
];

// ── Instalación: se guarda lo mínimo para poder arrancar sin conexión ──
self.addEventListener('install', ev => {
  ev.waitUntil(
    caches.open(CACHE_VERSION)
      .then(c => c.addAll(ESENCIALES))
      .catch(() => {})          // si algo no se puede guardar, se instala igual
      .then(() => self.skipWaiting())
  );
});

// ── Activación: se borran las cachés de versiones anteriores ──
self.addEventListener('activate', ev => {
  ev.waitUntil(
    caches.keys()
      .then(claves => Promise.all(
        claves.filter(k => k !== CACHE_VERSION).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── Pedidos ──
self.addEventListener('fetch', ev => {
  const req = ev.request;

  // Solo lecturas del propio sitio. Todo lo que va a Supabase, a las tipografías
  // o a cualquier otro dominio pasa de largo sin tocarse.
  if (req.method !== 'GET') return;
  let url;
  try { url = new URL(req.url); } catch (e) { return; }
  if (url.origin !== self.location.origin) return;

  const esPagina = req.mode === 'navigate' || /\.html?$/i.test(url.pathname);

  if (esPagina) {
    // El sistema: siempre se pide a la red. La caché se usa solo si falla.
    ev.respondWith(
      fetch(req)
        .then(res => {
          if (res && res.ok) {
            const copia = res.clone();
            caches.open(CACHE_VERSION).then(c => c.put(req, copia)).catch(() => {});
          }
          return res;
        })
        .catch(() =>
          caches.match(req).then(r => r || caches.match('./'))
        )
    );
    return;
  }

  // Íconos y manifiesto: de la caché, y se refrescan por detrás.
  ev.respondWith(
    caches.match(req).then(guardado => {
      const red = fetch(req).then(res => {
        if (res && res.ok) {
          const copia = res.clone();
          caches.open(CACHE_VERSION).then(c => c.put(req, copia)).catch(() => {});
        }
        return res;
      }).catch(() => guardado);
      return guardado || red;
    })
  );
});

// Permite forzar la actualización desde la página
self.addEventListener('message', ev => {
  if (ev.data === 'actualizar-ya') self.skipWaiting();
});
