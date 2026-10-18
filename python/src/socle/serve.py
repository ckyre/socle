"""Démarrage d'une application ASGI sur $PORT, en IPv4 et en IPv6 à la fois.

Sur Railway, le réseau privé est en IPv6 et le test de santé arrive en IPv4. Or « uvicorn --host :: » n'écoute
qu'en IPv6 (asyncio active IPV6_V6ONLY) : on crée donc nous-mêmes un socket double pile. HOST=0.0.0.0 force
l'IPv4 seul (machine sans IPv6).

Utilisation, dans `app/serve.py` :

    from socle.serve import run

    if __name__ == "__main__":
        run("app.main:app", name="Codex")
"""

from __future__ import annotations

import os
import socket
from typing import Any

# Réglages imposés à toutes les applications :
# - server_header=False : ne pas annoncer le serveur ;
# - proxy_headers=False : ne jamais croire X-Forwarded-For / X-Forwarded-Proto (seule la passerelle parle à l'app,
#   et l'IP réelle du client n'est pas une donnée de sécurité ici) ;
# - timeout_graceful_shutdown : un redéploiement ne coupe pas les requêtes en cours plus de 10 s.
SAFE_DEFAULTS: dict[str, Any] = {"server_header": False, "proxy_headers": False, "timeout_graceful_shutdown": 10}


def dual_stack_socket(host: str, port: int) -> socket.socket:
    """Socket TCP à l'écoute : IPv6 + IPv4 si `host` est une adresse IPv6 (« :: »), IPv4 seul sinon."""
    if ":" in host:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(2048)
    except OSError:
        sock.close()
        raise
    return sock


def run(app: str, *, name: str = "", default_port: int = 8000, **uvicorn_options: Any) -> None:
    """Lance `app` (« module:variable ») avec uvicorn sur [$HOST]:$PORT (défaut : [::]:default_port).

    Les options passées remplacent les réglages par défaut (SAFE_DEFAULTS) ; à réserver aux cas justifiés.
    """
    import uvicorn

    host = os.environ.get("HOST", "::")
    port = int(os.environ.get("PORT", str(default_port)))
    sock = dual_stack_socket(host, port)
    print(f"{name + ' : ' if name else ''}écoute sur [{host}]:{port}", flush=True)
    config = uvicorn.Config(app, **{**SAFE_DEFAULTS, **uvicorn_options})
    uvicorn.Server(config).run(sockets=[sock])
