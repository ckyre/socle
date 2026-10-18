# Socle

Code commun aux applications de la suite (Charge, Codex, Fund, Mijote, Vigie, Notifications, Fichiers, Portail).
Une correction faite ici, publiée dans une nouvelle version, profite à toutes les applications : il suffit de
mettre à jour la référence de version dans chacune (`scripts/mettre-a-jour.py`).

Le dépôt est public : il ne contient aucun secret. La sécurité repose sur les secrets de chaque déploiement
(GATEWAY_SECRET…), jamais sur le code.

## Contenu

| Élément | Rôle |
| --- | --- |
| `socle.serve` | Démarre une application ASGI sur `$PORT` en IPv4 et IPv6 (Railway : réseau privé IPv6, test de santé IPv4), sans en-tête `Server`, sans faire confiance aux en-têtes `X-Forwarded-*`. |
| `socle.passerelle` | Refuse toute requête qui ne porte pas le secret de la passerelle du portail (`X-Gateway-Secret`), sauf les chemins publics déclarés (test de santé). Ajoute `X-Robots-Tag`. Valide le secret au démarrage. Lit l'identité transmise (`Remote-User`, `Remote-Name`, `Remote-Email`, `Remote-Groups`). |
| `socle.transfert` | Export/import JSON d'une base vers une autre, en une transaction, uniquement vers une base vide. Inactif tant qu'une application ne le branche pas. |
| `css/socle.css` | Base CSS commune d'accessibilité : focus visible, `.sr-only` / `.visually-hidden`, mouvements réduits, `[hidden]`, `box-sizing`. Aucune couleur, police ni mise en page imposée. |

## Utilisation dans une application

**Python** (`requirements.txt`) — archive d'une version précise, vérifiée par son empreinte :

```
socle @ https://github.com/ckyre/socle/releases/download/v1.0.1/socle-1.0.1-py3-none-any.whl#sha256=<empreinte>
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
"socle": "https://github.com/ckyre/socle/releases/download/v1.0.1/socle-1.0.1.tgz"
```

```css
@import "tailwindcss";      /* le cas échéant */
@import "socle/socle.css";
:root { --socle-focus: var(--accent); }
```

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

```sh
cd python
pip install -e ".[serve,transfert]" -r requirements-test.txt
TEST_PG_URL=postgresql+psycopg://postgres@localhost/postgres pytest   # PostgreSQL facultatif
```
