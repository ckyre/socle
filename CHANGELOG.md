# Historique

## 1.0.0

Première version, qui remplace le code recopié dans chaque application :

- `socle.serve` : démarrage IPv4 + IPv6 avec réglages sûrs (`server_header=False`, `proxy_headers=False`).
- `socle.passerelle` : refus de toute requête sans le secret de la passerelle (middleware ASGI), validation du
  secret au démarrage (32 caractères minimum), lecture de l'identité transmise par le portail.
- `socle.transfert` : export/import JSON vérifié entre deux bases (pour une future migration ; rien d'actif par défaut).
- `socle.css` : base commune (focus visible, texte pour lecteurs d'écran, mouvements réduits, `[hidden]`…).
