import pytest
from fastapi import FastAPI, Request, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from socle.passerelle import (
    ROBOTS,
    ConfigurationError,
    GatewayMiddleware,
    Identity,
    check_secret,
    from_gateway,
    identity,
)

SECRET = "s" * 40
GOOD = {"X-Gateway-Secret": SECRET}


def make_app(**kw) -> FastAPI:
    app = FastAPI()
    app.add_middleware(GatewayMiddleware, **{"secret": SECRET, **kw})

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/me")
    def me(request: Request):
        u = identity(request.headers, SECRET)
        return None if u is None else {"username": u.username, "name": u.name, "admin": u.is_admin}

    @app.post("/api/items")
    def create():
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        await socket.accept()
        await socket.send_text("bonjour")
        await socket.close()

    return app


def test_requests_without_the_secret_are_refused():
    c = TestClient(make_app())
    for r in (c.get("/api/me"), c.post("/api/items"), c.get("/api/me", headers={"X-Gateway-Secret": "x" * 40}),
              c.get("/api/me", headers={"X-Gateway-Secret": SECRET[:-1]}), c.get("/inconnu")):
        assert r.status_code == 401
        assert r.json() == {"detail": "Accès réservé : passez par le portail."}
        assert r.headers["x-robots-tag"] == ROBOTS
    # Un en-tête d'identité seul ne suffit jamais.
    assert c.get("/api/me", headers={"Remote-User": "gabriel"}).status_code == 401


def test_gateway_requests_pass_and_carry_identity():
    c = TestClient(make_app())
    r = c.get("/api/me", headers={**GOOD, "Remote-User": "gabriel", "Remote-Name": "Gabriel%20Rouleau",
                                   "Remote-Groups": "admins,users"})
    assert r.status_code == 200
    assert r.json() == {"username": "gabriel", "name": "Gabriel Rouleau", "admin": True}
    assert r.headers["x-robots-tag"] == ROBOTS
    assert c.post("/api/items", headers=GOOD).json() == {"ok": True}
    # Passerelle sans utilisateur (ne devrait pas arriver) : aucune identité.
    assert c.get("/api/me", headers=GOOD).json() is None


def test_public_paths_and_disabled_mode():
    c = TestClient(make_app())
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/health/").status_code == 401  # correspondance exacte uniquement

    c = TestClient(make_app(enabled=lambda: False))
    r = c.get("/api/me")
    assert r.status_code == 200 and r.headers["x-robots-tag"] == ROBOTS

    c = TestClient(make_app(public_paths={"/api/health", "/api/items"}, status_code=403, detail="Non."))
    assert c.post("/api/items").status_code == 200
    r = c.get("/api/me")
    assert r.status_code == 403 and r.json() == {"detail": "Non."}


def test_missing_secret_fails_closed_and_is_read_per_request():
    current = {"secret": ""}
    c = TestClient(make_app(secret=lambda: current["secret"]))
    assert c.get("/api/me", headers={"X-Gateway-Secret": ""}).status_code == 401
    current["secret"] = SECRET
    assert c.get("/api/me", headers=GOOD).status_code == 200
    assert TestClient(make_app(secret=None)).get("/api/me", headers=GOOD).status_code == 401


def test_websocket():
    c = TestClient(make_app())
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws") as ws:
            ws.receive_text()
    with c.websocket_connect("/ws", headers=GOOD) as ws:
        assert ws.receive_text() == "bonjour"


def test_check_secret():
    assert check_secret(SECRET) == SECRET
    for bad in (None, "", "a" * 31, "a" * 31 + "é", "a" * 40 + " ", "a" * 40 + "/"):
        with pytest.raises(ConfigurationError):
            check_secret(bad)
    with pytest.raises(ConfigurationError, match="CHARGE_GATEWAY_SECRET"):
        check_secret("", "CHARGE_GATEWAY_SECRET")


def test_helpers_on_plain_mappings():
    assert from_gateway({"x-gateway-secret": SECRET}, SECRET)
    assert not from_gateway({"x-gateway-secret": SECRET}, "")
    assert not from_gateway({}, SECRET)
    u = identity({"x-gateway-secret": SECRET, "remote-user": " romy ", "remote-email": "r@x.fr"}, SECRET)
    assert u == Identity("romy", "romy", "r@x.fr", frozenset())
    assert not u.is_admin
