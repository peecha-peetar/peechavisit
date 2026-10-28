// sw.js - Service Worker پیچا ویزیت | آفلاین-First v2.0
'use strict';

const CACHE_NAME  = 'pv-shell-v4';
const API_PREFIX  = '/api/';

// فایل‌هایی که باید cache بشن (app shell)
const SHELL_FILES = [
    '/',
    '/index.html',
    '/login.html',
    '/app.js',
    '/manifest.json',
    '/icon-192.png',
    '/apple-touch-icon.png',
];

// ── نصب: cache همه فایل‌های shell ──
self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(SHELL_FILES))
            .then(() => self.skipWaiting())
    );
});

// ── فعال‌سازی: پاک کردن cache قدیمی ──
self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys
                .filter(k => k !== CACHE_NAME)
                .map(k => caches.delete(k))
            )
        ).then(() => self.clients.claim())
    );
});

// ── رهگیری درخواست‌ها ──
self.addEventListener('fetch', e => {
    const url = new URL(e.request.url);

    // ✅ POST و API → هرگز cache نشه، مستقیم به شبکه
    if (e.request.method !== 'GET' || url.pathname.startsWith(API_PREFIX)) {
        // اگه آفلاین و POST هست → بذار app.js handle کنه (IndexedDB)
        return;
    }

    // ✅ استراتژی Cache-First برای فایل‌های shell
    e.respondWith(
        caches.match(e.request).then(cached => {
            if (cached) {
                // از cache برگردون و در پس‌زمینه update کن
                if (navigator.onLine) {
                    e.waitUntil(
                        fetch(e.request)
                            .then(fresh => {
                                if (fresh && fresh.status === 200) {
                                    caches.open(CACHE_NAME)
                                        .then(c => c.put(e.request, fresh));
                                }
                            }).catch(() => {})
                    );
                }
                return cached;
            }

            // در cache نیست → از شبکه بگیر
            return fetch(e.request)
                .then(resp => {
                    // فقط فایل‌های موفق cache بشن
                    if (resp && resp.status === 200 && resp.type === 'basic') {
                        const clone = resp.clone();
                        caches.open(CACHE_NAME)
                            .then(c => c.put(e.request, clone));
                    }
                    return resp;
                })
                .catch(() => {
                    // آفلاین و در cache هم نیست
                    if (e.request.destination === 'document') {
                        return caches.match('/index.html');
                    }
                    return new Response('Offline', { status: 503 });
                });
        })
    );
});

// ── دریافت پیام از app ──
self.addEventListener('message', e => {
    if (e.data === 'SKIP_WAITING') self.skipWaiting();
    if (e.data === 'CLEAR_CACHE') {
        caches.delete(CACHE_NAME);
    }
});
