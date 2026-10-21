# Historique

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
