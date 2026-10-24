"""Notifications des applications : envoi au service Notifications, et tâche de fond périodique.

Envoi (bibliothèque standard seulement, appelable depuis n'importe quel fil) :

    from socle.notifications import Notifier, portal_username

    notifier = Notifier(settings.notify_url, settings.notify_key)
    if notifier.configured:
        notifier.send(["romy"], "Romy a ajouté lait à la liste", url="https://mijote.exemple.fr/courses")

Le service range la notification dans l'historique du portail et l'envoie sur les canaux de chaque destinataire
(e-mail, Telegram, push). Les destinataires sont des identifiants du portail : `portal_username("portail:romy")`.

Tâche de fond (vérifications régulières : « y a-t-il quelque chose à envoyer ? ») :

    from socle.notifications import Periodic

    tache = Periodic("rappels", 60, verifier)   # verifier() appelée toutes les 60 s, erreurs journalisées
    tache.start()  … tache.stop()

Une tâche périodique idempotente (« envoyer si ce n'est pas déjà fait ») rattrape d'elle-même un passage manqué
pendant un redéploiement, sans planificateur.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass

log = logging.getLogger("socle.notifications")

PORTAL_PREFIX = "portail:"
TITLE_MAX = 160
BODY_MAX = 4000


class NotificationError(Exception):
    """Envoi refusé ou impossible. `permanent` : inutile de réessayer tel quel (clé refusée, données invalides)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status
        self.permanent = status in (400, 401, 403, 422)


def portal_username(sub: str | None) -> str | None:
    """Identifiant du portail d'un utilisateur enregistré sous « portail:<identifiant> », sinon None."""
    if sub and sub.startswith(PORTAL_PREFIX) and len(sub) > len(PORTAL_PREFIX):
        return sub[len(PORTAL_PREFIX):]
    return None


def shorten(text: str, limit: int, one_line: bool = False) -> str:
    text = " ".join(text.split()) if one_line else text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def enumerate_fr(items: Iterable[str], limit: int = 4) -> str:
    """« lait, œufs et beurre » ; au-delà de `limit` : « lait, œufs, beurre et 2 autres »."""
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    if len(items) > limit:
        rest = len(items) - (limit - 1)
        return f"{', '.join(items[: limit - 1])} et {rest} autres"
    return f"{', '.join(items[:-1])} et {items[-1]}"


@dataclass(frozen=True)
class Notifier:
    """Client du service Notifications (POST /v1/notifications, clé de l'application)."""

    url: str | None
    key: str | None
    timeout: float = 10.0

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key)

    def send(self, to: str | Iterable[str], title: str, body: str = "", url: str | None = None,
             level: str = "info") -> dict:
        """Envoie une notification ; renvoie la réponse du service ({"sent_to": […], "unknown": […]})."""
        if not self.configured:
            raise NotificationError("service de notifications non configuré (URL et clé)")
        recipients = to if isinstance(to, str) else sorted(set(to))
        if not recipients:
            raise NotificationError("aucun destinataire")
        payload: dict = {"to": recipients, "title": shorten(title, TITLE_MAX, one_line=True), "body": shorten(body, BODY_MAX),
                         "level": level}
        if url:
            payload["url"] = url
        request = urllib.request.Request(
            self.url.rstrip("/") + "/v1/notifications",  # type: ignore[union-attr]
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as r:  # noqa: S310 (adresse de la configuration)
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read() or b"{}").get("detail") or e.reason
            except ValueError:
                detail = e.reason
            raise NotificationError(f"service de notifications : {e.code} {detail}", e.code) from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise NotificationError(f"service de notifications injoignable ({e.__class__.__name__})") from e


class Periodic:
    """Appelle `fn()` toutes les `interval` secondes dans un fil d'arrière-plan, jusqu'à `stop()`.

    Une exception est journalisée sans arrêter la tâche. Premier appel après `delay` secondes (laisse
    l'application finir de démarrer : migrations, etc.).
    """

    def __init__(self, name: str, interval: float, fn: Callable[[], object], delay: float = 5.0):
        self.name, self.interval, self.fn, self.delay = name, interval, fn, delay
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> Periodic:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name=f"socle-{self.name}", daemon=True)
            self._thread.start()
            log.info("Tâche « %s » : toutes les %d s", self.name, self.interval)
        return self

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def run_once(self) -> None:
        try:
            self.fn()
        except Exception:  # la tâche doit survivre à une erreur ponctuelle (base ou service indisponible)
            log.exception("Tâche « %s » : échec", self.name)

    def _run(self) -> None:
        if self._stop.wait(self.delay):
            return
        while True:
            self.run_once()
            if self._stop.wait(self.interval):
                return
