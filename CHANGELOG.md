# Historique

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
