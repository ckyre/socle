# Historique

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
