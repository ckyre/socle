# Historique

## 1.4.0

- **Animation d'ouverture de la suite** (« Éclosion + geste ») dans le greffon `socle/vite` : `socle()` l'ajoute
  d'office ; `ouverture()` seule pour les applications qui n'utilisent pas `/socle-sw.js`. Au build, `index.html`
  reçoit en ligne l'icône (`public/favicon.svg`), le CSS de la mise en scène commune (tassement, rebond, ouverture)
  suivi du geste propre à l'application (`frontend/ouverture.css`), et un petit script synchrone :
  - démarrage à froid seulement (`sessionStorage`), `?ouverture` dans l'adresse pour la rejouer ;
  - « réduire les animations » du système : simple fondu ;
  - l'application s'ouvre dès que React a rempli `#root`, pas avant 0,75 s (fin du geste) ; secours à 8 s ;
  - fond du calque : `background_color` du manifest (option `fond`).
  Option `externe: true` (portail) : CSS et script dans `/socle-ouverture.css` et `/socle-ouverture.js`, pour une
  CSP sans `'unsafe-inline'`. Le geste : groupes `class="o-…"` dans `favicon.svg`, keyframes dans `ouverture.css`
  en pourcentages d'un cycle de 2,2 s (`CYCLE_OUVERTURE`), entre 8 % et 34 %.

## 1.3.0

- **`socle.notifications`** (Python, bibliothèque standard seulement) : `Notifier` envoie une notification au
  service Notifications (clé de l'application, erreurs typées : `NotificationError.permanent`) ;
  `Periodic` appelle une vérification toutes les N secondes dans un fil (« y a-t-il quelque chose à envoyer ? ») ;
  `portal_username("portail:romy")`, `enumerate_fr(["lait", "œufs", "beurre"])` → « lait, œufs et beurre ».
  Utilisé par Mijote (liste de courses, menu vide), Logis (entretien du jour) et Fund (budget du mois).
- `socle/push` garde le service worker propre à une application (Mijote, hors ligne) au lieu de le remplacer par
  `/socle-sw.js` ; ce service worker importe `socle/sw.js` pour afficher les notifications.
- `scripts/mettre-a-jour.py` : met aussi à jour les lignes `socle @ …` suivies d'un commentaire (elles restaient à
  l'ancienne version).

## 1.2.4

- `<socle-push>` : quand les notifications ne sont pas activées, le bouton « Activer » se place sur la ligne
  « Cet appareil », à la place de la pastille « Désactivées » (supprimée).

## 1.2.3

- `<socle-push>` redessiné : pictogramme de l'appareil (téléphone ou écran), titre « Cet appareil », nom de l'appareil,
  pastille d'état (Activées, Désactivées, Bloquées, Indisponible). Une ligne d'aide courte n'apparaît que lorsqu'il
  faut agir (écran d'accueil, autorisation).

## 1.2.2

- `<socle-push>` : les propriétés `base` et `titre` acceptent une valeur. React 19 passe les attributs d'un élément
  personnalisé comme propriétés : `<socle-push base="…">` plantait la page (« setting getter-only property »).
  Un changement d'attribut après l'affichage est pris en compte.

## 1.2.1

- Retrait de la dépendance « peer » facultative à `vite` : elle faisait échouer `npm install` dans certaines
  applications (erreur interne de npm « Cannot read properties of null (reading 'edgesOut') »). Le greffon
  `socle/vite` n'importe rien de Vite.
- `scripts/mettre-a-jour.py` : une application en échec n'arrête plus les suivantes ; elles sont listées à la fin.

## 1.2.0

- **Notifications push** (Web Push), côté navigateur :
  - `socle/push` : élément `<socle-push>` (état de l'appareil, activer, envoyer un essai, désactiver ; message
    d'aide sur iPhone hors écran d'accueil ou quand les notifications sont bloquées), fonctions `activerPush`,
    `desactiverPush`, `testerPush`, `etatPush`, `synchroniserPush`, `effacerPastille` ; types TypeScript, y compris
    pour `<socle-push>` dans le JSX ;
  - `socle/vite` : greffon qui sert le service worker commun sous `/socle-sw.js` (développement et build) ;
  - service worker : affiche la notification, ouvre son lien (dans la fenêtre déjà ouverte si possible), pose la
    pastille de l'icône, réabonne l'appareil quand le navigateur renouvelle son abonnement.
- `scripts/icones.mjs` : icônes d'écran d'accueil (iOS 512 px, Android 192/512 et maskable), manifest et balises
  d'`index.html` de chaque application.
- Le paquet npm est un module ES (`"type": "module"`).

## 1.1.0

- **CSS commun de la suite, construit sur Tailwind 4, mobile d'abord** (`socle/suite.css`). C'est la charpente
  que Hotte, Logis, Besace, Mijote et Vigie recopiaient chacune, unifiée :
  - jetons d'identité dans `@theme` (`--color-ground`, `--color-ink`, `--color-accent`, `--font-display`,
    `--radius-control`, `--container-app`…), avec des couleurs dérivées par `color-mix` ; ils créent leurs
    utilitaires (`bg-accent-soft`, `rounded-card`, `p-gutter`, `max-w-app`…) ;
  - coquille mobile : `.app`, `.screen`, `.topbar`, `.nav` / `.nav-floating`, `.action-bar`, `.fab`,
    `.sheet` (fenêtre centrée à partir de 640px, `<dialog>` accepté), `.toast`, zones sûres et place des barres
    fixes calculées automatiquement ;
  - composants : `.btn` (+ `primary`, `dark`, `soft`, `ghost`, `danger`, `dashed`, `sm`, `lg`, `block`),
    `.icon-btn`, `.link-btn`, `.field` / `.label` / `.input` (16px, sans zoom iOS), `.search`, `.check`,
    `.switch`, `.chip(s)`, `.segmented`, `.pill`, `.badge-count`, `.card`, `.list-row`, `.empty`,
    `.icon-tile`, `.avatar`, `.progress`, `.banner`, `.spinner`, textes `.h1`–`.h3`, `.eyebrow`, `.hint` ;
  - `.stepper` (compteur − valeur +) ;
  - primitives d'agencement `stack`, `row`, `spread`, `cluster`, `fill`, `divided` (couche components, pour
    qu'une classe de l'application puisse les ajuster) ;
  - `--socle-line-height` (1,5 par défaut, `normal` pour une interface dense) ;
  - sélecteurs d'éléments en `:where()` (`:where(a, button).card`…) : une classe de l'application les ajuste sans
    surenchère de spécificité ;
  - états par attributs ARIA (`aria-pressed`, `aria-current`, `aria-invalid`, `aria-busy`…).
- `socle/kit.css` : le même contenu sans `@import "tailwindcss"`.
- `socle/socle.css` (accessibilité seule) inchangé : les applications non migrées continuent de fonctionner.
- `tailwindcss` ^4.1 en dépendance « peer » facultative.
- `scripts/verifier-css.mjs` (lancé en CI) et page d'exemple `exemples/` avec les identités des applications.
- Migrées sur ce socle : Mijote, Vigie, Hotte, Logis, Besace, Portail (CSS maison → Tailwind 4 + socle), Fund et
  Charge (déjà en Tailwind : thème rapporté aux jetons de la suite).

## 1.0.1

- `socle.css` réduit à l'accessibilité (box-sizing, `[hidden]`, focus visible, `.sr-only`, mouvements réduits) :
  les règles sur les champs (`font`/`color: inherit`), les images et le `body` pouvaient changer l'apparence
  d'une application (texte de champ illisible sur fond clair).

## 1.0.0

Première version, qui remplace le code recopié dans chaque application :

- `socle.serve` : démarrage IPv4 + IPv6 avec réglages sûrs (`server_header=False`, `proxy_headers=False`).
- `socle.passerelle` : refus de toute requête sans le secret de la passerelle (middleware ASGI), validation du
  secret au démarrage (32 caractères minimum), lecture de l'identité transmise par le portail.
- `socle.transfert` : export/import JSON vérifié entre deux bases (pour une future migration ; rien d'actif par défaut).
- `socle.css` : base commune (focus visible, texte pour lecteurs d'écran, mouvements réduits, `[hidden]`…).
