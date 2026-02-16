/**
 * Certify Intel - Service Worker
 * Enables offline functionality and push notifications.
 */

const CACHE_VERSION = 'v8.3.1';
const CACHE_NAME = `certify-intel-${CACHE_VERSION}`;
const RUNTIME_CACHE = `certify-intel-runtime-${CACHE_VERSION}`;

// Static assets to cache for offline use
const PRECACHE_ASSETS = [
    '/',
    '/index.html',
    '/login.html',
    '/styles.css',
    '/app_v2.js',
    '/sales_marketing.js',
    '/enhanced_analytics.js',
    '/visualizations.js',
    '/manifest.json',
    '/app_icon.jpg',
    '/browser_tab_icon.jpg'
];

// API endpoints to cache for offline
const CACHE_API_ENDPOINTS = [
    '/api/competitors',
    '/api/sales-marketing/dimensions',
    '/api/products/coverage',
    '/api/data-quality/overview'
];

// PERF-SW: TTL-based API response caching (in milliseconds)
const API_CACHE_TTL = {
    '/api/competitors': 5 * 60 * 1000,           // 5 min
    '/api/dashboard': 2 * 60 * 1000,             // 2 min
    '/api/data-quality/overview': 5 * 60 * 1000, // 5 min
    '/api/sales-marketing/dimensions': 5 * 60 * 1000,
    '/api/products/coverage': 5 * 60 * 1000,
    '/api/news-feed': 2 * 60 * 1000,
    '/api/analytics': 3 * 60 * 1000
};
const DEFAULT_API_TTL = 2 * 60 * 1000; // 2 min default

// Max cache size in bytes (50 MB)
const MAX_CACHE_SIZE_BYTES = 50 * 1024 * 1024;

// Install event - precache static assets
self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Install');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[ServiceWorker] Pre-caching static assets');
                return cache.addAll(PRECACHE_ASSETS);
            })
            .then(() => self.skipWaiting())
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activate');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((cacheName) => cacheName !== CACHE_NAME && cacheName !== RUNTIME_CACHE)
                    .map((cacheName) => caches.delete(cacheName))
            );
        }).then(() => self.clients.claim())
    );
});

// Listen for skip waiting message from app
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip cross-origin requests
    if (url.origin !== location.origin) {
        return;
    }

    // For API requests
    if (url.pathname.startsWith('/api/')) {
        // PERF-SW: Mutations (POST/PUT/DELETE) invalidate related caches
        if (request.method !== 'GET') {
            event.respondWith(
                fetch(request).then(response => {
                    invalidateRelatedCaches(url.pathname);
                    return response;
                })
            );
            return;
        }
        // GET requests use TTL-aware network-first strategy
        event.respondWith(networkFirstWithTTL(request));
        return;
    }

    // For static assets, use cache-first strategy
    event.respondWith(cacheFirst(request));
});

// Cache-first strategy
async function cacheFirst(request) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
        return cachedResponse;
    }

    try {
        const networkResponse = await fetch(request);

        // Cache successful responses
        if (networkResponse.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }

        return networkResponse;
    } catch (error) {
        console.log('[ServiceWorker] Fetch failed:', error);
        return new Response('Offline - Content not available', {
            status: 503,
            statusText: 'Service Unavailable'
        });
    }
}

// PERF-SW: TTL-aware network-first strategy for API calls
async function networkFirstWithTTL(request) {
    const url = new URL(request.url);
    const pathname = url.pathname;

    try {
        const networkResponse = await fetch(request);

        // Cache successful GET requests with timestamp metadata
        if (networkResponse.ok && request.method === 'GET') {
            const cache = await caches.open(RUNTIME_CACHE);

            // Clone response and store with timestamp header
            const headers = new Headers(networkResponse.headers);
            headers.set('sw-cache-time', Date.now().toString());

            const cachedBody = await networkResponse.clone().arrayBuffer();
            const timestampedResponse = new Response(cachedBody, {
                status: networkResponse.status,
                statusText: networkResponse.statusText,
                headers: headers
            });

            cache.put(request, timestampedResponse);

            // Enforce cache size limit
            enforceCacheSizeLimit();
        }

        return networkResponse;
    } catch (error) {
        // Network failed - try cache with TTL check
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            const cacheTime = parseInt(cachedResponse.headers.get('sw-cache-time') || '0');
            const ttl = getTTLForPath(pathname);
            const age = Date.now() - cacheTime;

            // Serve stale cache if within TTL, or if offline (any age is better than nothing)
            if (cacheTime === 0 || age < ttl || !navigator.onLine) {
                return cachedResponse;
            }
        }

        return new Response(JSON.stringify({
            error: 'Offline',
            message: 'Unable to fetch data. Please check your connection.'
        }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

// Legacy alias for compatibility
async function networkFirst(request) {
    return networkFirstWithTTL(request);
}

/**
 * Get TTL for a given API path by matching against configured prefixes.
 */
function getTTLForPath(pathname) {
    for (const [prefix, ttl] of Object.entries(API_CACHE_TTL)) {
        if (pathname.startsWith(prefix)) {
            return ttl;
        }
    }
    return DEFAULT_API_TTL;
}

/**
 * Invalidate cached API responses related to a mutation path.
 * E.g., POST /api/competitors/5 invalidates GET /api/competitors
 */
async function invalidateRelatedCaches(mutationPath) {
    try {
        const cache = await caches.open(RUNTIME_CACHE);
        const keys = await cache.keys();

        // Extract the base resource path (e.g., /api/competitors from /api/competitors/5/dimensions)
        const segments = mutationPath.split('/').filter(Boolean);
        const basePath = '/' + segments.slice(0, 3).join('/');

        const deletions = keys.filter(req => {
            const cachedPath = new URL(req.url).pathname;
            return cachedPath.startsWith(basePath);
        }).map(req => cache.delete(req));

        await Promise.all(deletions);
    } catch (err) {
        // Cache invalidation is best-effort
    }
}

/**
 * Enforce maximum cache size by evicting oldest entries first.
 */
async function enforceCacheSizeLimit() {
    try {
        const cache = await caches.open(RUNTIME_CACHE);
        const keys = await cache.keys();

        // Estimate total size by summing response body sizes
        let totalSize = 0;
        const entries = [];

        for (const req of keys) {
            const res = await cache.match(req);
            if (res) {
                const blob = await res.clone().blob();
                const cacheTime = parseInt(res.headers.get('sw-cache-time') || '0');
                entries.push({ request: req, size: blob.size, cacheTime: cacheTime });
                totalSize += blob.size;
            }
        }

        if (totalSize <= MAX_CACHE_SIZE_BYTES) return;

        // Sort by oldest first and evict until under limit
        entries.sort((a, b) => a.cacheTime - b.cacheTime);

        for (const entry of entries) {
            if (totalSize <= MAX_CACHE_SIZE_BYTES) break;
            await cache.delete(entry.request);
            totalSize -= entry.size;
        }
    } catch (err) {
        // Size enforcement is best-effort
    }
}

// Push notification event
self.addEventListener('push', (event) => {
    console.log('[ServiceWorker] Push received');

    let data = { title: 'Certify Intel', body: 'You have a new notification' };

    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data.body = event.data.text();
        }
    }

    const options = {
        body: data.body,
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/badge-72.png',
        vibrate: [100, 50, 100],
        data: data.url || '/app',
        actions: [
            { action: 'view', title: 'View' },
            { action: 'dismiss', title: 'Dismiss' }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(data.title || 'Certify Intel', options)
    );
});

// Notification click event
self.addEventListener('notificationclick', (event) => {
    console.log('[ServiceWorker] Notification click');
    event.notification.close();

    if (event.action === 'dismiss') {
        return;
    }

    // Open the app or focus existing window
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // If a window is already open, focus it
                for (const client of clientList) {
                    if (client.url.includes('/app') && 'focus' in client) {
                        return client.focus();
                    }
                }
                // Otherwise, open a new window
                if (clients.openWindow) {
                    return clients.openWindow(event.notification.data || '/app');
                }
            })
    );
});

// Background sync for offline submissions
self.addEventListener('sync', (event) => {
    console.log('[ServiceWorker] Background sync');

    if (event.tag === 'sync-win-loss') {
        event.waitUntil(syncWinLossData());
    }
});

async function syncWinLossData() {
    // Sync any offline win/loss data when back online
    const cache = await caches.open(RUNTIME_CACHE);
    // Implementation would send cached offline submissions to server
    console.log('[ServiceWorker] Syncing offline data...');
}
