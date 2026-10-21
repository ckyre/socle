# CSS de la suite

Un seul CSS pour toutes les applications, **construit sur Tailwind 4** et pensé **mobile d'abord**. Chaque
application garde son identité (couleurs, polices, rayons) en réglant quelques jetons. Elle écrit le reste avec
les utilitaires Tailwind, et ajoute son propre CSS si besoin.

```css
/* src/styles.css */
@import "socle/suite.css";

@theme {
  --color-ground: #f6f1e7;
  --color-surface: #fffdf8;
  --color-ink: #2b2620;
  --color-accent: #a8412a;
  --color-ok: #5e6b3a;
  --font-sans: "Instrument Sans", system-ui, sans-serif;
  --font-display: "Fraunces", Georgia, serif;
  --radius-control: 0.625rem;
}

/* Règles d'éléments de l'application : dans la couche base, pour ne pas écraser les composants. */
@layer base {
  a { color: var(--color-accent); }
}

/* Ajustements des composants du socle et composants propres à l'application : dans la couche components,
   après ceux du socle (ils les ajustent) et sous les utilitaires Tailwind (qui peuvent encore les corriger). */
@layer components {
  .btn { min-height: 52px; }
  .leader .dots { flex: 1; border-bottom: 1.5px dotted var(--color-field); }
}
```

```ts
// vite.config.ts
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({ plugins: [react(), tailwindcss()] });
```

Page d'exemple avec tous les composants et les identités de Hotte, Logis, Besace, Mijote, Vigie et Charge :
`node scripts/verifier-css.mjs`, puis ouvrir `exemples/dist/index.html`.

## Fichiers

| Fichier | Contenu | Couche |
| --- | --- | --- |
| `suite.css` | **Point d'entrée** : `@import "tailwindcss"` + `kit.css` | — |
| `kit.css` | Tout le socle sans Tailwind, pour une app qui importe Tailwind elle-même (`@import "tailwindcss" source(…)`) | — |
| `jetons.css` | Jetons de la suite dans `@theme` : couleurs, polices, rayons, hauteurs | theme |
| `socle.css` | Accessibilité : focus visible, `.sr-only`, mouvements réduits, `[hidden]` (inchangé depuis 1.0.1) | base |
| `base.css` | Ajouts au preflight : fond et encre du thème, `100dvh`, curseur des boutons | base |
| `mise-en-page.css` | Coquille mobile : `.app`, `.screen`, `.topbar`, `.nav`, `.action-bar`, `.fab`, `.sheet`, `.toast` | components |
| `composants.css` | `.btn`, `.icon-btn`, `.link-btn`, `.input`, `.switch`, `.chip`, `.segmented`, `.pill`, `.card`, `.list-row`… | components |
| `utilitaires.css` | Primitives d'agencement `stack`, `row`, `spread`, `cluster`, `fill`, `divided` | components |

Priorités : thème < base < composants < utilitaires < CSS hors couche. Un utilitaire corrige toujours un
composant (`class="btn btn-primary w-full"`).

**Où mettre le CSS d'une application** (leçon de la migration) :

- les règles d'éléments (`a`, `code`, `button:disabled`…) dans `@layer base` : hors couche, un simple `a { color }`
  l'emporterait sur `.btn` ou `.nav a` du socle, quelle que soit la spécificité ;
- les ajustements de composants et les classes propres à l'application dans `@layer components` : déclarés après
  le socle, ils l'emportent à spécificité égale, tout en laissant les états du socle (`.chip[aria-pressed="true"]`)
  et les utilitaires Tailwind passer devant ;
- quand on change la couleur de base d'un composant (`.link-btn { color: … }`), redonner celle de ses variantes
  (`.link-btn-danger`), déclarées avant dans le socle.

## Jetons

Ils sont définis dans le `@theme` de Tailwind, donc chacun crée ses utilitaires (`bg-accent-soft`,
`text-muted`, `border-line`, `rounded-card`, `p-gutter`, `min-h-tap`, `h-control`, `max-w-app`, `font-display`,
`text-caption`, `shadow-float`…). Les composants n'utilisent que ces jetons.

**À régler** : `--color-ground` (fond), `--color-surface` (cartes, champs), `--color-ink` (texte),
`--color-accent` (action principale) et `--color-on-accent`, `--color-ok`, `--color-warn`, `--color-danger`,
`--font-sans`, `--font-display`.

**Dérivés** : `ink-2`, `muted`, `faint`, `field`, `line`, `surface-2`, `accent-soft`, `accent-strong`,
`*-soft`, `overlay`. Ils sont calculés par `color-mix` à partir des précédents, donc un thème sombre ne
demande que quatre couleurs. On peut les fixer à la main (par exemple `--color-accent-ink` si l'accent est trop
clair pour servir de couleur de texte).

**Forme** : `--radius-control` (boutons, champs), `--radius-card`, `--radius-sheet`, `--container-app` (largeur
de la colonne, 35rem ; 75rem pour une app de bureau comme Portail), `--spacing-gutter`, `--spacing-control`…

**Réglages sans utilitaire** (sur `:root`) : `--socle-scheme: dark`, `--socle-control-border: none` (champs et
boutons sans bord, style Logis/Vigie), `--socle-card-border: none`, `--socle-display-weight`,
`--socle-line-height` (1,5 par défaut comme Tailwind ; `normal` pour une interface dense, comme les applications
mobiles de la suite — y ajouter dans `@theme` `--text-xs--line-height: inherit;` et `--text-sm--line-height:
inherit;` pour que `text-xs` / `text-sm` ne changent que la taille).

Thème sombre (Charge) :

```css
@theme {
  --color-ground: #08090a;
  --color-surface: #101214;
  --color-ink: #ededea;
  --color-accent: oklch(0.86 0.19 118);
  --color-on-accent: #08090a;
}
:root { --socle-scheme: dark; }
```

## Conventions

- **Mobile d'abord** : les styles de base visent un téléphone ; les écrans plus larges s'ajoutent avec les
  variantes de Tailwind (`md:`, `@variant sm`). Toute cible tactile fait au moins 44px, et les champs font
  16px pour qu'iOS ne zoome pas à la saisie (Hotte, Logis et Vigie avaient des champs à 15px).
- **États ARIA, pas de classes d'état** : `aria-pressed="true"` (pastille, segment), `aria-current="page"`
  (onglet), `aria-checked`, `aria-invalid="true"` (champ en erreur), `aria-busy="true"` (bouton en cours),
  `disabled`. Le style suit donc ce qu'entend un lecteur d'écran.
- **Variantes préfixées** : `.btn .btn-primary .btn-sm`, `.pill .pill-ok`, `.link-btn .link-btn-danger`.
- **Survol réservé aux souris** : `@variant hover` ne s'applique pas au toucher (pas de survol « collé »).
- **Barres fixes** : `--socle-bottom-offset` est calculé selon ce qui est affiché (`.nav`, `.nav-floating`,
  `.action-bar`) ; `.screen`, `.toast` et `.fab` se placent au-dessus, zones sûres (encoche) comprises.

## Gabarit d'écran

```html
<div class="app">
  <main class="screen">
    <header class="spread">
      <div class="stack gap-1">
        <p class="eyebrow">Mercredi 21 octobre</p>
        <h1 class="h1">Recettes</h1>
      </div>
      <button class="icon-btn icon-btn-surface" aria-label="Compte">…</button>
    </header>

    <div class="chips chips-scroll" role="group" aria-label="Filtrer">
      <button class="chip" aria-pressed="true">Tout</button>
      <button class="chip" aria-pressed="false">Rapide</button>
    </div>

    <ul class="card card-list">
      <li><a class="list-row" href="/r/1"><span class="fill row-title truncate">Blanquette</span>
        <span class="pill pill-ok">Ce soir</span></a></li>
    </ul>
  </main>

  <button class="fab" aria-label="Ajouter">+</button>

  <nav class="nav" aria-label="Navigation principale">   <!-- ou "nav nav-floating" -->
    <a href="/" aria-current="page"><span class="nav-icon">…<span class="badge-count">3</span></span>Accueil</a>
    <a href="/menu"><span class="nav-icon">…</span>Menu</a>
  </nav>
</div>

<!-- Feuille : monte du bas sur téléphone, fenêtre centrée à partir de 640px -->
<div class="sheet-backdrop">
  <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="t">
    <div class="sheet-handle" aria-hidden="true"></div>
    <h2 class="sheet-title" id="t">Nouvelle recette</h2>
    …
    <div class="sheet-footer"><button class="btn btn-primary">Enregistrer</button></div>
  </div>
</div>
```

`<dialog class="sheet">` ouvert avec `showModal()` fonctionne aussi (fond par `::backdrop`).

## Migration d'une application

1. Ajouter Tailwind : `npm i -D tailwindcss @tailwindcss/vite`, le plugin dans `vite.config.ts` (Charge, qui
   passe par PostCSS, peut garder `@tailwindcss/postcss`).
2. Mettre à jour la référence du socle (`scripts/mettre-a-jour.py v1.1.0`).
3. Dans `styles.css` : remplacer `@import "socle/socle.css"` (et `@import "tailwindcss"`) par
   `@import "socle/suite.css"`, puis traduire le bloc `:root { --paper…; --ink… }` en `@theme { --color-… }`.
4. Supprimer de `styles.css` tout ce que le socle couvre (remise à zéro, structure, boutons, champs, pastilles,
   cartes, navigation, feuille, message). Garder ce qui est propre à l'application (héros, frise, graphique…), en
   le réécrivant avec les jetons (`var(--color-accent)` au lieu de `var(--mer)`).
5. Renommer les classes dans le JSX (tableau ci-dessous), puis vérifier chaque écran sur téléphone.

| Avant | Avec le socle |
| --- | --- |
| `.grow` | `fill` (ou `flex-1 min-w-0`) |
| `.select`, `.textarea` (Mijote) | `input` (sur `<select>` / `<textarea>`) |
| `.note` (Mijote, Besace) | `hint` |
| `.btn` vert/rouge par défaut (Mijote, Besace) | `btn btn-primary` |
| `.btn.ghost`, `.btn.dark`, `.btn.small`, `.btn.block` | `btn-ghost`, `btn-dark`, `btn-sm`, `btn-block` |
| `.btn-big` (Logis, Vigie), `.btn-primary` haut (Hotte) | `btn btn-primary btn-lg` |
| `.btn-red`, `.btn-sage` | `btn btn-primary` (l'accent de l'app) |
| `.dashed-btn`, `.btn-dashed`, `.add-row` | `btn btn-dashed btn-block` |
| `.round-btn` (Logis, Vigie) | `icon-btn icon-btn-surface` |
| `.icon-btn.accent`, `.done-btn` | `icon-btn icon-btn-primary` |
| `.icon-btn.plain` | `icon-btn` |
| `.link-btn.danger`, `.link-btn.muted` | `link-btn link-btn-danger`, `link-btn link-btn-muted` |
| `.chip.on`, `.chip.dark`, `.chip.on.green` (Hotte, Logis) | `chip` + `aria-pressed="true"` |
| `.chip.add`, `.chip.dashed` | `chip chip-add` |
| `.chips.scroll` | `chips chips-scroll` |
| `.seg button.on`, `.seg … [aria-pressed]` (Logis, Vigie) | `segmented` + `aria-pressed="true"` |
| `.toggle` (Vigie), `button.switch[aria-checked]` (Mijote) | `switch` (case native `role="switch"` ou bouton `aria-checked`) |
| `.input.soft`, `.input.invalid` | `input input-soft`, `input` + `aria-invalid="true"` |
| `.card.pad`, `.card.list` | `card card-pad`, `card card-list` |
| `.pill-green`, `.pill.mer`, `.buy-tag` | `pill pill-ok`, `pill pill-accent`, `pill pill-warn` |
| `.banner.error`, `.alert` (Hotte) | `banner banner-error` |
| `.submit-bar` (Hotte, Logis), `.action-bar .inner` (Vigie, Besace) | `action-bar` (enfants directs) |
| `.nav` + `.nav-inner` (Hotte, Besace, Mijote) | `nav` (`.nav-inner` reste accepté) |
| `.nav` flottante (Logis, Vigie), `.nav-pill` | `nav nav-floating`, `nav-icon` |
| `.sheet-grip` (Besace) | `sheet-handle` |
| `.sheet-submit` (Vigie) | `sheet-footer` |
| `.spinner` texte de chargement (Mijote, Besace) | `hint` ; `spinner` est désormais un indicateur tournant |
| `.small`, `.xsmall`, `.muted`, `.center`, `.ellipsis` | `text-caption`, `text-xs`, `text-muted`, `text-center`, `truncate` |
| `.mono`, `.num` | `font-mono tabular-nums`, `tabular-nums` |

Pour **Codex** (bureau, parchemin) et **Portail** (bureau, formulaires) : régler `--container-app: 75rem`. Les
composants s'utilisent tels quels ; les décors propres (cadres en bronze, arbre, tableaux d'administration)
restent dans leur CSS. **Charge** et **Fund**, déjà en Tailwind, remplacent leurs couleurs `@theme` par les
jetons de la suite (`--color-text` → `--color-ink`, `--color-lime` → `--color-accent`…).
