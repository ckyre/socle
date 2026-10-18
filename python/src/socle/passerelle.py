"""Accès réservé à la passerelle du portail.

En production, une application n'a aucun domaine public : seule la passerelle du portail l'atteint, après avoir
vérifié la session (ou le jeton d'accès personnel) de l'utilisateur. La passerelle :

- retire des requêtes reçues d'Internet tout en-tête d'identité (Remote-*) et tout X-Gateway-Secret ;
- ajoute l'identité vérifiée (Remote-User, Remote-Name, Remote-Email, Remote-Groups) ;
- ajoute le secret partagé X-Gateway-Secret (variable GATEWAY_SECRET).

Les en-têtes d'identité ne sont donc fiables QUE si la requête porte le bon secret. Ce module refuse tout le reste :
même un domaine public laissé ouvert par erreur ne donnerait accès à rien.

Utilisation (FastAPI / Starlette) :

    from socle.passerelle import GatewayMiddleware, check_secret, identity

    check_secret(settings.gateway_secret)                      # au démarrage : refuse un secret absent ou faible
    app.add_middleware(GatewayMiddleware, secret=lambda: get_settings().gateway_secret)

    user = identity(request.headers, get_settings().gateway_secret)   # Identity ou None
"""

from __future__ import annotations

import hmac
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from urllib.parse import unquote

MIN_SECRET_LENGTH = 32
SECRET_HEADER = "x-gateway-secret"
ROBOTS = "noindex, nofollow, noarchive, nosnippet"
DEFAULT_PUBLIC_PATHS = frozenset({"/api/health"})
DEFAULT_DETAIL = "Accès réservé : passez par le portail."
# Même jeu de caractères que celui accepté par la passerelle (gateway/entrypoint.sh du portail).
_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ConfigurationError(RuntimeError):
    """Configuration dangereuse : l'application ne doit pas démarrer."""


def check_secret(secret: str | None, variable: str = "GATEWAY_SECRET") -> str:
    """Valide le secret partagé avec la passerelle ; lève ConfigurationError s'il est absent ou trop faible."""
    if not secret:
        raise ConfigurationError(f"{variable} est obligatoire (même valeur que la passerelle du portail)")
    if len(secret) < MIN_SECRET_LENGTH:
        raise ConfigurationError(f"{variable} doit faire au moins {MIN_SECRET_LENGTH} caractères")
    if not _SECRET_RE.match(secret):
        raise ConfigurationError(f"{variable} : lettres, chiffres, _ et - uniquement")
    return secret


def from_gateway(headers: Mapping[str, str], secret: str | None) -> bool:
    """La requête porte-t-elle le secret de la passerelle ? (comparaison en temps constant)"""
    if not secret:
        return False
    received = headers.get(SECRET_HEADER) or ""
    return hmac.compare_digest(received.encode(), secret.encode())


@dataclass(frozen=True)
class Identity:
    """Utilisateur du portail, tel que transmis par la passerelle."""

    username: str
    name: str
    email: str
    groups: frozenset[str]

    @property
    def is_admin(self) -> bool:
        return "admins" in self.groups


def identity(headers: Mapping[str, str], secret: str | None) -> Identity | None:
    """Identité de l'utilisateur, ou None si la requête ne vient pas de la passerelle ou n'en porte aucune."""
    if not from_gateway(headers, secret):
        return None
    username = (headers.get("remote-user") or "").strip()
    if not username:
        return None
    return Identity(
        username=username,
        # Le portail encode le nom (en-têtes HTTP : ASCII uniquement).
        name=unquote(headers.get("remote-name") or "").strip() or username,
        email=(headers.get("remote-email") or "").strip(),
        groups=frozenset(g for g in (headers.get("remote-groups") or "").split(",") if g),
    )


class _ScopeHeaders(Mapping[str, str]):
    """En-têtes d'un scope ASGI, accessibles en minuscules (sans dépendre de Starlette)."""

    def __init__(self, raw: Iterable[tuple[bytes, bytes]]):
        self._h: dict[str, str] = {}
        for k, v in raw:
            self._h.setdefault(k.decode("latin-1").lower(), v.decode("latin-1"))

    def __getitem__(self, key: str) -> str:
        return self._h[key.lower()]

    def __iter__(self):
        return iter(self._h)

    def __len__(self) -> int:
        return len(self._h)


def _value(v):
    return v() if callable(v) else v


class GatewayMiddleware:
    """Middleware ASGI : refuse toute requête sans le secret de la passerelle (sauf `public_paths`).

    - `secret` : la valeur, ou une fonction qui la renvoie (relue à chaque requête, pratique pour les tests) ;
    - `enabled` : False (ou fonction) pour le mode local sans passerelle ; X-Robots-Tag est ajouté dans tous les cas ;
    - `public_paths` : chemins exacts accessibles sans la passerelle (test de santé de Railway).

    Activé sans secret configuré, il refuse tout (échec sûr).
    """

    def __init__(
        self,
        app,
        *,
        secret: str | Callable[[], str | None] | None,
        enabled: bool | Callable[[], bool] = True,
        public_paths: Iterable[str] = DEFAULT_PUBLIC_PATHS,
        status_code: int = 401,
        detail: str = DEFAULT_DETAIL,
    ):
        self.app = app
        self.secret = secret
        self.enabled = enabled
        self.public_paths = frozenset(public_paths)
        self.status_code = status_code
        self.body = json.dumps({"detail": detail}, ensure_ascii=False).encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        allowed = (
            not _value(self.enabled)
            or scope.get("path", "") in self.public_paths
            or from_gateway(_ScopeHeaders(scope.get("headers", [])), _value(self.secret))
        )
        if not allowed:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            await send({
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(self.body)).encode()),
                    (b"x-robots-tag", ROBOTS.encode()),
                    (b"cache-control", b"no-store"),
                ],
            })
            await send({"type": "http.response.body", "body": self.body})
            return

        async def send_with_robots(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if not any(k.lower() == b"x-robots-tag" for k, _ in headers):
                    headers.append((b"x-robots-tag", ROBOTS.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_robots if scope["type"] == "http" else send)
