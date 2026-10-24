/* Service worker commun de la suite : affiche les notifications push et ouvre leur lien.
 *
 * Servi à la racine de chaque application (/socle-sw.js, par le greffon Vite « socle/vite ») et enregistré par
 * « socle/push ». Le message vient du service de notifications : { title, body, url, tag, app, level, badge }.
 *
 * L'adresse d'abonnement (?base=…) est passée dans l'URL du script : elle sert à réabonner l'appareil quand le
 * navigateur renouvelle son abonnement (pushsubscriptionchange).
 *
 * Une application qui a son propre service worker l'importe au lieu d'utiliser /socle-sw.js :
 *     import "socle/sw.js";   // dans src/sw.ts (vite-plugin-pwa, workbox…)
 */

const BASE = new URL(self.location.href).searchParams.get("base") || "/__notifications/push";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

function lire(event) {
  if (!event.data) return {};
  try {
    return event.data.json();
  } catch {
    return { body: event.data.text() };
  }
}

self.addEventListener("push", (event) => {
  const m = lire(event);
  // iOS retire l'abonnement d'une application qui reçoit un push sans afficher de notification : on affiche toujours.
  const affichage = self.registration.showNotification(m.title || "Notification", {
    body: m.body || "",
    tag: m.tag,
    lang: "fr",
    icon: "/icone-192.png",
    badge: "/icone-192.png",
    requireInteraction: m.level === "important",
    data: { url: m.url || "/" },
  });
  const pastille =
    typeof m.badge === "number" && "setAppBadge" in self.navigator
      ? (m.badge > 0 ? self.navigator.setAppBadge(m.badge) : self.navigator.clearAppBadge()).catch(() => {})
      : Promise.resolve();
  event.waitUntil(Promise.all([affichage, pastille]));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const cible = new URL(event.notification.data?.url || "/", self.location.origin);
  event.waitUntil(
    (async () => {
      const fenetres = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      if (cible.origin === self.location.origin) {
        const ouverte = fenetres.find((c) => new URL(c.url).origin === cible.origin);
        if (ouverte) {
          await ouverte.focus();
          if ("navigate" in ouverte && ouverte.url !== cible.href) await ouverte.navigate(cible.href).catch(() => {});
          return;
        }
      }
      await self.clients.openWindow(cible.href);
    })(),
  );
});

self.addEventListener("pushsubscriptionchange", (event) => {
  const options = event.oldSubscription?.options;
  if (!options?.applicationServerKey) return;
  event.waitUntil(
    (async () => {
      const abonnement = event.newSubscription || (await self.registration.pushManager.subscribe(options));
      await fetch(`${BASE}/subscriptions`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...abonnement.toJSON(), label: "" }),
      });
    })().catch(() => {}),
  );
});
