# Socle

Code commun aux applications de la suite (Besace, Charge, Codex, Fund, Hotte, Logis, Mijote, Vigie, Notifications, Fichiers,
Portail).
Une correction faite ici, publiée dans une nouvelle version, profite à toutes les applications : il suffit de
mettre à jour la référence de version dans chacune (`scripts/mettre-a-jour.py`).

Le dépôt est public : il ne contient aucun secret. La sécurité repose sur les secrets de chaque déploiement
(GATEWAY_SECRET…), jamais sur le code.

## Contenu

| Élément | Rôle |
| --- | --- |
| `socle.serve` | Démarre une application ASGI sur `$PORT` en IPv4 et IPv6 (Railway : réseau privé IPv6, test de santé IPv4), sans en-tête `Server`, sans faire confiance aux en-têtes `X-Forwarded-*`. |
| `socle.passerelle` | Refuse toute requête qui ne porte pas le secret de la passerelle du portail (`X-Gateway-Secret`), sauf les chemins publics déclarés (test de santé). Ajoute `X-Robots-Tag`. Valide le secret au démarrage. Lit l'identité transmise (`Remote-User`, `Remote-Name`, `Remote-Email`, `Remote-Groups`). |
| `socle.notifications` | Envoi d'une notification au service Notifications (`Notifier`) et tâche de fond périodique (`Periodic`) pour les rappels planifiés. |
| `socle.transfert` | Export/import JSON d'une base vers une autre, en une transaction, uniquement vers une base vide. Inactif tant qu'une application ne le branche pas. |
| `css/suite.css` | CSS commun de la suite, construit sur Tailwind 4 et mobile d'abord : jetons d'identité dans `@theme`, coquille mobile (`.app`, `.screen`, `.nav`, `.sheet`…), composants (`.btn`, `.input`, `.card`…) et primitives d'agencement. Voir [`css/README.md`](css/README.md). |
| `js/push.js` (`socle/push`) | Notifications push côté navigateur : élément `<socle-push>` (activer, tester, désactiver sur cet appareil), fonctions `activerPush`, `etatPush`…, pastille de l'icône effacée à l'ouverture. |
| `js/sw.js`, `js/vite.js` (`socle/vite`) | Service worker commun (affiche les notifications, ouvre leur lien, pose la pastille) et greffon Vite qui le sert sous `/socle-sw.js`. |
| `scripts/icones.mjs` | Icônes d'écran d'accueil iOS et Android de chaque application, tirées de son `favicon.svg`. |
| `css/socle.css` | Base d'accessibilité seule (déjà incluse dans `suite.css`) : focus visible, `.sr-only` / `.visually-hidden`, mouvements réduits, `[hidden]`, `box-sizing`. |

## Utilisation dans une application

**Python** (`requirements.txt`) — archive d'une version précise, vérifiée par son empreinte :

```
socle @ https://github.com/ckyre/socle/releases/download/v1.1.0/socle-1.1.0-py3-none-any.whl#sha256=<empreinte>
```

```python
# app/serve.py
from socle.serve import run

if __name__ == "__main__":
    run("app.main:app", name="Codex")
```

```python
# app/main.py
from socle.passerelle import GatewayMiddleware, check_secret, identity

if settings.portail:
    check_secret(settings.gateway_secret)          # refuse de démarrer avec un secret absent ou faible
app.add_middleware(GatewayMiddleware, secret=lambda: get_settings().gateway_secret,
                   enabled=lambda: get_settings().portail)

user = identity(request.headers, get_settings().gateway_secret)   # Identity(username, name, email, groups) ou None
```

**CSS** (`package.json`, l'empreinte est enregistrée dans `package-lock.json`) :

```
"socle": "https://github.com/ckyre/socle/releases/download/v1.1.0/socle-1.1.0.tgz"
```

```css
@import "socle/suite.css";   /* Tailwind 4 + tout le socle */
@theme {                     /* identité de l'application */
  --color-accent: #a8412a;
  --font-display: "Fraunces", Georgia, serif;
}
```

Avec le plugin `@tailwindcss/vite` (ou `@tailwindcss/postcss`). Guide complet, jetons, composants et
correspondance des anciennes classes : [`css/README.md`](css/README.md). Les applications qui n'ont pas encore
migré gardent `@import "socle/socle.css";` (accessibilité seule), qui reste disponible.

**Notifications push** (applications qui envoient des notifications) :

```ts
// vite.config.ts
import socle from "socle/vite";
export default defineConfig({ plugins: [react(), tailwindcss(), socle()] });   // sert /socle-sw.js

// main.tsx
import "socle/push";

// là où l'utilisateur règle ses notifications
<socle-push />
```

L'abonnement passe par `/__notifications/push` sur le sous-domaine de l'application : la passerelle vérifie la
session et le transmet au service de notifications (`NOTIFICATIONS_UPSTREAM`). Rien à faire côté backend. Sur iPhone,
`<socle-push>` explique qu'il faut d'abord ajouter l'application à l'écran d'accueil.

## Publier une version

1. Modifier le code, ajouter des tests, décrire le changement dans `CHANGELOG.md`.
2. Mettre le même numéro dans `python/src/socle/__init__.py` et `package.json`.
3. `git commit`, `git tag vX.Y.Z`, `git push --follow-tags`.

GitHub Actions lance les tests (dont PostgreSQL et IPv6), construit les deux archives et publie la version avec
le fichier `SHA256SUMS`. Ensuite, depuis le dossier qui contient tous les dépôts :

```sh
python socle/scripts/mettre-a-jour.py vX.Y.Z
```

Le script met à jour la référence et l'empreinte dans chaque application ; il reste à tester et pousser chacune.

## Développement

CSS : vérification (compilation Tailwind, jetons tous définis, couches) et page d'exemple
`exemples/dist/index.html` :

```sh
npm install --no-save tailwindcss@4.3.3 @tailwindcss/node@4.3.3
node scripts/verifier-css.mjs
```

Python :

```sh
cd python
pip install -e ".[serve,transfert]" -r requirements-test.txt
TEST_PG_URL=postgresql+psycopg://postgres@localhost/postgres pytest   # PostgreSQL facultatif
```
