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
// Une application qui a déjà son propre service worker l'utilise : il suffit qu'il importe « socle/sw.js ».

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
  // Une application qui a déjà son propre service worker (hors ligne…) le garde : il doit importer
  // « socle/sw.js » pour afficher les notifications. Le remplacer par /socle-sw.js casserait l'application.
  const existant = await navigator.serviceWorker.getRegistration("/");
  const script = (existant?.active ?? existant?.waiting ?? existant?.installing)?.scriptURL ?? "";
  if (script && new URL(script).pathname !== SERVICE_WORKER) return navigator.serviceWorker.ready;
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

// État affiché : pastille (texte, variante) et, seulement quand l'utilisateur doit agir, une ligne d'aide courte.
const ETATS = {
  actif: { pastille: "Activées", variante: "pill-ok" },
  inactif: {}, // pas de pastille : le bouton « Activer » prend sa place
  refuse: { pastille: "Bloquées", variante: "pill-warn", aide: "À autoriser dans les réglages de l'appareil." },
  installer: { pastille: "Indisponible", variante: "", aide: "Ajoutez d'abord l'application à l'écran d'accueil." },
  "non-supporte": { pastille: "Indisponible", variante: "", aide: "Navigateur non compatible." },
  "non-configure": { pastille: "Indisponible", variante: "", aide: "Push non configuré sur le serveur." },
};

// Pictogrammes Lucide (licence ISC, lucide.dev) : téléphone ou écran selon l'appareil.
const PICTOS = {
  telephone: '<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>',
  ecran: '<rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
};

function picto(nom) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  for (const [k, v] of Object.entries({ viewBox: "0 0 24 24", width: "20", height: "20", fill: "none", stroke: "currentColor",
    "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" })) svg.setAttribute(k, v);
  svg.innerHTML = PICTOS[nom];
  return svg;
}

function estMobile() {
  return estIOS() || /Android/.test(navigator.userAgent);
}

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
    return this.getAttribute("titre") || "Cet appareil";
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
    const etat = cle ? ETATS[cle] : null;
    const el = (tag, classe, texte) => {
      const n = document.createElement(tag);
      if (classe) n.className = classe;
      if (texte != null) n.textContent = texte;
      return n;
    };

    const carte = el("div", "socle-push stack");
    carte.style.gap = "12px";

    // Ligne d'identité : pictogramme de l'appareil, titre, nom de l'appareil, pastille d'état.
    const tete = el("div", "row");
    Object.assign(tete.style, { gap: "12px", alignItems: "center" });
    const tuile = el("span", "icon-tile");
    tuile.append(picto(estMobile() ? "telephone" : "ecran"));
    const textes = el("div", "fill");
    Object.assign(textes.style, { minWidth: "0", display: "flex", flexDirection: "column", gap: "2px" });
    textes.append(el("strong", "", this.titre));
    const sous = el("span", "hint", etat?.aide ?? nomAppareil());
    sous.style.margin = "0";
    textes.append(sous);
    tete.append(tuile, textes);
    if (cle === "inactif") {
      tete.append(this.#bouton("Activer", "btn-primary", async () => {
        await activerPush({ base: this.base });
        return { texte: "Notifications activées." };
      }));
    } else if (etat?.pastille) {
      tete.append(el("span", `pill ${etat.variante}`.trim(), etat.pastille));
    }
    carte.append(tete);

    const actions = el("div", "row");
    Object.assign(actions.style, { flexWrap: "wrap", gap: "8px" });
    if (cle === "actif") {
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
      const m = el("p", this.#message.erreur ? "banner banner-error" : "banner banner-ok", this.#message.texte);
      m.setAttribute("role", this.#message.erreur ? "alert" : "status");
      m.style.margin = "0";
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
