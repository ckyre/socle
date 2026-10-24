// Notifications push des applications de la suite, côté navigateur.
//
//   import "socle/push";                  // enregistre <socle-push> et efface la pastille à l'ouverture
//   <socle-push></socle-push>             // carte « Notifications sur cet appareil » (activer, tester, désactiver)
//
// Fonctions (pour une interface sur mesure) : etatPush, activerPush, desactiverPush, testerPush, synchroniserPush.
//
// L'abonnement passe par la passerelle (chemin /__notifications/push de l'application, session vérifiée), qui le
// transmet au service de notifications : une notification de l'application arrive avec son icône et ouvre
// l'application. Le portail utilise son propre relais : <socle-push base="/api/notifications/push">.
//
// iOS / iPadOS (16.4+) : uniquement dans une application ajoutée à l'écran d'accueil, et l'activation doit suivre un
// geste de l'utilisateur (bouton). Le service worker (/socle-sw.js) est servi par le greffon « socle/vite ».

export const BASE_PAR_DEFAUT = "/__notifications/push";
export const SERVICE_WORKER = "/socle-sw.js";

function estIOS() {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function estInstallee() {
  return window.matchMedia?.("(display-mode: standalone)").matches || navigator.standalone === true;
}

/** « ok », « installer » (iOS : ajouter d'abord à l'écran d'accueil) ou « non-supporte ». */
export function pushPossible() {
  const api = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  if (estIOS() && !estInstallee()) return "installer";
  if (!api || !window.isSecureContext) return "non-supporte";
  return "ok";
}

/** Nom lisible de l'appareil, montré dans la liste des appareils du portail. */
export function nomAppareil() {
  const ua = navigator.userAgent;
  const appareil = /iPhone/.test(ua) ? "iPhone" : /iPad/.test(ua) || (estIOS() && !/iPhone/.test(ua)) ? "iPad"
    : /Android/.test(ua) ? "Android" : /Mac OS X/.test(ua) ? "Mac" : /Windows/.test(ua) ? "Windows"
    : /Linux/.test(ua) ? "Linux" : "Appareil";
  const navigateur = /Edg\//.test(ua) ? "Edge" : /Firefox\//.test(ua) ? "Firefox" : /SamsungBrowser/.test(ua) ? "Samsung Internet"
    : /Chrome\//.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : "";
  if (estIOS()) return estInstallee() ? `${appareil} (écran d'accueil)` : appareil;
  return navigateur ? `${navigateur} sur ${appareil}` : appareil;
}

async function requete(url, methode = "GET", corps) {
  const r = await fetch(url, {
    method: methode,
    credentials: "same-origin",
    headers: corps === undefined ? {} : { "Content-Type": "application/json" },
    body: corps === undefined ? undefined : JSON.stringify(corps),
  });
  let donnees = null;
  try {
    donnees = await r.json();
  } catch {
    /* réponse vide */
  }
  if (!r.ok) {
    const detail = typeof donnees?.detail === "string" ? donnees.detail : null;
    throw new Error(r.status === 401 ? "Session expirée : rechargez la page." : detail || `Erreur ${r.status}`);
  }
  return donnees;
}

function octets(base64url) {
  const b64 = base64url.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (base64url.length % 4)) % 4);
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

function memeCle(a, b) {
  if (!a || !b) return false;
  const x = new Uint8Array(a);
  return x.length === b.length && x.every((v, i) => v === b[i]);
}

async function enregistrement(base) {
  const url = `${SERVICE_WORKER}?base=${encodeURIComponent(base)}`;
  await navigator.serviceWorker.register(url, { scope: "/" });
  return navigator.serviceWorker.ready;
}

async function abonnementActuel() {
  if (pushPossible() !== "ok") return null;
  const reg = await navigator.serviceWorker.getRegistration("/");
  return reg ? reg.pushManager.getSubscription() : null;
}

/**
 * État pour cet appareil : { possible, configure, permission, abonne }.
 * `configure` : le serveur a une clé VAPID ; `permission` : « default », « granted » ou « denied ».
 */
export async function etatPush({ base = BASE_PAR_DEFAUT } = {}) {
  const possible = pushPossible();
  if (possible !== "ok") return { possible, configure: null, permission: null, abonne: false };
  const [serveur, abonnement] = await Promise.all([requete(base), abonnementActuel()]);
  return {
    possible,
    configure: !!serveur?.enabled,
    permission: Notification.permission,
    abonne: !!abonnement && Notification.permission === "granted",
  };
}

/** À appeler directement depuis un clic (iOS l'exige pour la demande de permission). */
export async function activerPush({ base = BASE_PAR_DEFAUT, label = nomAppareil() } = {}) {
  if (pushPossible() !== "ok") throw new Error("Les notifications push ne sont pas disponibles ici.");
  // Permission d'abord, avant toute autre attente : le geste de l'utilisateur doit encore être « actif ».
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error(permission === "denied"
      ? "Notifications refusées : autorisez-les dans les réglages de l'appareil, puis réessayez."
      : "Notifications non autorisées.");
  }
  const [serveur, reg] = await Promise.all([requete(base), enregistrement(base)]);
  if (!serveur?.enabled || !serveur.public_key) throw new Error("Les notifications push ne sont pas configurées sur le serveur.");
  const cle = octets(serveur.public_key);
  let abonnement = await reg.pushManager.getSubscription();
  if (abonnement && !memeCle(abonnement.options?.applicationServerKey, cle)) {
    await abonnement.unsubscribe(); // clé du serveur changée : l'ancien abonnement ne marchera plus
    abonnement = null;
  }
  abonnement ??= await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: cle });
  await requete(`${base}/subscriptions`, "POST", { ...abonnement.toJSON(), label });
  return abonnement;
}

export async function desactiverPush({ base = BASE_PAR_DEFAUT } = {}) {
  const abonnement = await abonnementActuel();
  if (!abonnement) return;
  await requete(`${base}/unsubscribe`, "POST", { endpoint: abonnement.endpoint }).catch(() => {});
  await abonnement.unsubscribe();
}

/** Envoie une notification d'essai à cet appareil. Renvoie le nombre d'appareils atteints. */
export async function testerPush({ base = BASE_PAR_DEFAUT } = {}) {
  const abonnement = await abonnementActuel();
  const r = await requete(`${base}/test`, "POST", { endpoint: abonnement?.endpoint ?? null });
  return r?.reached ?? 0;
}

/** Redonne au serveur l'abonnement de cet appareil (changement d'utilisateur, abonnement oublié par le serveur). */
export async function synchroniserPush({ base = BASE_PAR_DEFAUT, label = nomAppareil() } = {}) {
  if (pushPossible() !== "ok" || Notification.permission !== "granted") return;
  const abonnement = await abonnementActuel();
  if (abonnement) {
    await enregistrement(base); // met à jour le service worker si le socle a changé
    await requete(`${base}/subscriptions`, "POST", { ...abonnement.toJSON(), label });
  }
}

/** Retire la pastille de l'icône (posée par le service worker à l'arrivée d'une notification). */
export function effacerPastille() {
  if ("clearAppBadge" in navigator) navigator.clearAppBadge().catch(() => {});
}

// --- <socle-push> -----------------------------------------------------------------------------

const MESSAGES = {
  "non-supporte": "Ce navigateur ne reçoit pas de notifications push.",
  installer: "Sur iPhone et iPad, ajoutez d'abord l'application à l'écran d'accueil (Partager → « Sur l'écran d'accueil »), puis ouvrez-la depuis son icône.",
  "non-configure": "Les notifications push ne sont pas configurées sur le serveur.",
  refuse: "Notifications bloquées pour cette application : autorisez-les dans les réglages de l'appareil.",
  inactif: "Recevez les notifications de cette application sur cet appareil, même quand elle est fermée.",
  actif: "Activées sur cet appareil. Les canaux de chaque application se règlent dans le portail.",
};

class SoclePush extends HTMLElement {
  #etat = null;
  #occupe = false;
  #message = null; // { texte, erreur }

  static observedAttributes = ["base", "titre"];

  // React 19 passe les attributs d'un élément personnalisé comme propriétés quand elles existent : chaque
  // propriété a donc un mutateur, qui la reporte sur l'attribut.
  get base() {
    return this.getAttribute("base") || BASE_PAR_DEFAUT;
  }

  set base(valeur) {
    if (valeur == null) this.removeAttribute("base");
    else this.setAttribute("base", String(valeur));
  }

  get titre() {
    return this.getAttribute("titre") || "Notifications sur cet appareil";
  }

  set titre(valeur) {
    if (valeur == null) this.removeAttribute("titre");
    else this.setAttribute("titre", String(valeur));
  }

  connectedCallback() {
    if (!this.style.display) this.style.display = "block";
    this.#rendre();
    this.#charger(true);
  }

  attributeChangedCallback(nom, avant, apres) {
    if (!this.isConnected || avant === apres) return;
    if (nom === "base") this.#charger(true);
    else this.#rendre();
  }

  async #charger(synchroniser = false) {
    try {
      this.#etat = await etatPush({ base: this.base });
      if (synchroniser && this.#etat.abonne) synchroniserPush({ base: this.base }).catch(() => {});
    } catch (e) {
      this.#etat = { possible: "ok", configure: null, permission: null, abonne: false };
      this.#message = { texte: e.message, erreur: true };
    }
    this.#rendre();
  }

  async #agir(action) {
    this.#occupe = true;
    this.#message = null;
    this.#rendre();
    try {
      this.#message = await action();
    } catch (e) {
      this.#message = { texte: e.message, erreur: true };
    }
    this.#occupe = false;
    await this.#charger();
  }

  #bouton(texte, classe, action) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = `btn btn-sm ${classe}`;
    b.textContent = texte;
    b.disabled = this.#occupe;
    b.addEventListener("click", () => this.#agir(action));
    return b;
  }

  #rendre() {
    const e = this.#etat;
    const cle = !e ? null : e.possible !== "ok" ? e.possible : e.configure === false ? "non-configure"
      : e.permission === "denied" ? "refuse" : e.abonne ? "actif" : "inactif";

    const carte = document.createElement("div");
    carte.className = "socle-push stack";
    carte.style.gap = "10px";

    const tete = document.createElement("div");
    tete.className = "spread";
    const titre = document.createElement("strong");
    titre.textContent = this.titre;
    tete.append(titre);
    if (cle === "actif") {
      const pastille = document.createElement("span");
      pastille.className = "pill pill-ok";
      pastille.textContent = "Activées";
      tete.append(pastille);
    }
    carte.append(tete);

    const texte = document.createElement("p");
    texte.className = "hint";
    texte.style.margin = "0";
    texte.textContent = cle ? MESSAGES[cle] : "Chargement…";
    carte.append(texte);

    const actions = document.createElement("div");
    actions.className = "row";
    actions.style.flexWrap = "wrap";
    actions.style.gap = "8px";
    if (cle === "inactif") {
      actions.append(this.#bouton("Activer", "btn-primary", async () => {
        await activerPush({ base: this.base });
        return { texte: "Notifications activées." };
      }));
    } else if (cle === "actif") {
      actions.append(
        this.#bouton("Envoyer un essai", "btn-soft", async () => {
          const n = await testerPush({ base: this.base });
          return n ? { texte: "Essai envoyé : il arrive dans quelques secondes." }
            : { texte: "L'essai n'a atteint aucun appareil : désactivez puis réactivez.", erreur: true };
        }),
        this.#bouton("Désactiver", "btn-ghost", async () => {
          await desactiverPush({ base: this.base });
          return { texte: "Notifications désactivées sur cet appareil." };
        }),
      );
    }
    if (actions.childElementCount) carte.append(actions);

    if (this.#message) {
      const m = document.createElement("p");
      m.className = this.#message.erreur ? "banner banner-error" : "banner banner-ok";
      m.setAttribute("role", this.#message.erreur ? "alert" : "status");
      m.style.margin = "0";
      m.textContent = this.#message.texte;
      carte.append(m);
    }
    this.replaceChildren(carte);
  }
}

if (typeof window !== "undefined") {
  if (!customElements.get("socle-push")) customElements.define("socle-push", SoclePush);
  effacerPastille();
  document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && effacerPastille());
}
