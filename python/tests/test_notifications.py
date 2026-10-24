import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from socle.notifications import NotificationError, Notifier, Periodic, enumerate_fr, portal_username


@pytest.fixture
def service():
    """Faux service Notifications : enregistre les requêtes ; `answer` fixe la réponse."""
    state = {"calls": [], "answer": (202, {"sent_to": ["romy"], "unknown": []})}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["calls"].append({"path": self.path, "auth": self.headers["Authorization"], "body": body})
            code, out = state["answer"]
            data = json.dumps(out).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{srv.server_port}"
    yield state
    srv.shutdown()


def test_send_posts_to_the_service_with_the_app_key(service):
    n = Notifier(service["url"] + "/", "k" * 40)
    out = n.send(["romy", "romy", "gabriel"], "Romy a ajouté\n lait", "Ligne 1\nLigne 2", url="https://x.fr/c")
    assert out == {"sent_to": ["romy"], "unknown": []}
    call = service["calls"][0]
    assert call["path"] == "/v1/notifications" and call["auth"] == "Bearer " + "k" * 40
    assert call["body"] == {"to": ["gabriel", "romy"], "title": "Romy a ajouté lait", "body": "Ligne 1\nLigne 2",
                            "level": "info", "url": "https://x.fr/c"}


def test_long_titles_are_shortened(service):
    Notifier(service["url"], "k").send("all", "x" * 300)
    assert len(service["calls"][0]["body"]["title"]) == 160


@pytest.mark.parametrize("code,permanent", [(401, True), (422, True), (429, False), (503, False)])
def test_errors_are_reported(service, code, permanent):
    service["answer"] = (code, {"detail": "non"})
    with pytest.raises(NotificationError) as e:
        Notifier(service["url"], "k").send(["romy"], "t")
    assert e.value.status == code and e.value.permanent is permanent and "non" in str(e.value)


def test_unreachable_or_unconfigured():
    with pytest.raises(NotificationError):
        Notifier("http://127.0.0.1:9", "k", timeout=2).send(["romy"], "t")
    assert not Notifier(None, "k").configured
    with pytest.raises(NotificationError):
        Notifier("", "").send(["romy"], "t")


def test_helpers():
    assert portal_username("portail:romy") == "romy"
    assert portal_username("dev:romy") is None and portal_username("portail:") is None and portal_username(None) is None
    assert enumerate_fr(["lait"]) == "lait"
    assert enumerate_fr(["lait", "œufs", "beurre"]) == "lait, œufs et beurre"
    assert enumerate_fr(["a", "b", "c", "d", "e", "f"]) == "a, b, c et 3 autres"


def test_periodic_runs_until_stopped_and_survives_errors():
    calls = []

    def fn():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("panne ponctuelle")

    t = Periodic("essai", 0.05, fn, delay=0).start()
    time.sleep(0.3)
    t.stop()
    n = len(calls)
    assert n >= 3
    time.sleep(0.15)
    assert len(calls) == n
