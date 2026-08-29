// Panel de Agentes — Service Worker
// Enables Web Push notifications in background

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('push', (event) => {
  let data = { title: 'Panel de Agentes', body: 'Notificación', icon: '/static/favicon.png' };
  try {
    if (event.data) {
      data = event.data.json();
    }
  } catch (e) { /* ignore */ }

  const options = {
    body: data.body,
    icon: data.icon || '/static/favicon.png',
    badge: '/static/favicon.png',
    tag: data.tag || 'agent-alert',
    requireInteraction: true,
    vibrate: [200, 100, 200],
    data: { url: data.url || '/' },
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.openWindow(url)
  );
});