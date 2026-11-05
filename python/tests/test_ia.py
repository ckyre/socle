import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from socle.ia import (BudgetAtteint, ClientFactice, ClientIA, CleRefusee, EntreeInvalide, ErreurIA, Indisponible,
                      SortieInvalide, TacheInconnue, client_ia)

SORTIE = {"discipline": "course", "duree_min": 55}


@pytest.fixture
def service():
    """Faux service IA : enregistre les requêtes ; `reponses` (liste) fixe les réponses successives."""
    state = {"appels": [], "reponses": []}

    class H(BaseHTTPRequestHandler):
        def _repondre(self):
            longueur = int(self.headers.get("Content-Length") or 0)
            corps = json.loads(self.rfile.read(longueur)) if longueur else None
            state["appels"].append({"methode": self.command, "chemin": self.path, "auth": self.headers["Authorization"],
                                    "idem": self.headers.get("Idempotency-Key"), "corps": corps})
            code, out = state["reponses"].pop(0) if state["reponses"] else (200, {})
            data = json.dumps(out).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = _repondre

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{srv.server_port}"
    yield state
    srv.shutdown()


def client(service, **kw):
    return ClientIA(service["url"] + "/", "k" * 40, pause_reprise=0, **kw)


def ok(resultat=SORTIE):
    return 200, {"id": "a1", "tache": "charge.seance", "version": 2, "resultat": resultat,
                 "usage": {"modele": "claude-haiku-5-5", "cout_usd": 0.0001}, "duree_ms": 900}


def erreur(status, code, **details):
    return status, {"erreur": {"code": code, "message": "message du service", **details}}


def test_tache(service):
    service["reponses"] = [ok()]
    r = client(service).tache("charge.seance", {"texte": "footing"}, utilisateur="romy")
    assert r.resultat == SORTIE and r.version == 2 and r.usage["modele"] == "claude-haiku-5-5" and r.duree_ms == 900
    appel = service["appels"][0]
    assert appel["methode"] == "POST" and appel["chemin"] == "/v1/taches/charge.seance"
    assert appel["auth"] == "Bearer " + "k" * 40 and appel["idem"]
    assert appel["corps"] == {"entree": {"texte": "footing"}, "utilisateur": "romy"}


def test_cle_d_idempotence_fournie(service):
    service["reponses"] = [ok()]
    client(service).tache("charge.seance", {}, cle_idempotence="seance-42")
    assert service["appels"][0]["idem"] == "seance-42"
    assert "utilisateur" not in service["appels"][0]["corps"]


@pytest.mark.parametrize("reponse,classe,permanent", [
    (erreur(400, "entree_invalide", champs=["texte"]), EntreeInvalide, True),
    (erreur(401, "cle_invalide"), CleRefusee, True),
    (erreur(403, "tache_interdite"), CleRefusee, True),
    (erreur(404, "tache_inconnue"), TacheInconnue, True),
    (erreur(422, "sortie_invalide"), SortieInvalide, False),
    (erreur(429, "budget_atteint"), BudgetAtteint, False),
    (erreur(504, "delai_depasse"), Indisponible, False),
    ((500, {"pas": "le format"}), Indisponible, False),
])
def test_erreurs_typees(service, reponse, classe, permanent):
    service["reponses"] = [reponse, reponse]  # une erreur 5xx est reprise une fois
    with pytest.raises(classe) as e:
        client(service).tache("charge.seance", {})
    assert e.value.permanent is permanent and e.value.status == reponse[0]
    if reponse[0] == 400:
        assert e.value.details == {"champs": ["texte"]} and e.value.message == "message du service"


def test_une_reprise_si_indisponible_avec_la_meme_cle(service):
    service["reponses"] = [erreur(503, "anthropic_indisponible"), ok()]
    assert client(service).tache("charge.seance", {}).resultat == SORTIE
    premier, second = service["appels"]
    assert premier["idem"] == second["idem"]


def test_pas_plus_d_une_reprise(service):
    service["reponses"] = [erreur(503, "anthropic_indisponible"), erreur(503, "anthropic_indisponible")]
    with pytest.raises(Indisponible):
        client(service).tache("charge.seance", {})
    assert len(service["appels"]) == 2


def test_pas_de_reprise_apres_un_delai_depasse(service):
    service["reponses"] = [erreur(504, "delai_depasse")]
    with pytest.raises(Indisponible):
        client(service).tache("charge.seance", {})
    assert len(service["appels"]) == 1


def test_injoignable():
    c = ClientIA("http://127.0.0.1:9", "k", timeout=2, pause_reprise=0)
    with pytest.raises(Indisponible) as e:
        c.tache("charge.seance", {})
    assert e.value.code == "injoignable"


def test_non_configure():
    c = client_ia("", None)
    assert not c.configured
    with pytest.raises(ErreurIA):
        c.tache("charge.seance", {})


def test_lots(service):
    service["reponses"] = [
        (202, {"id": "l1", "tache": "charge.bilan", "statut": "en_cours", "elements": 2}),
        (200, {"id": "l1", "tache": "charge.bilan", "statut": "termine", "elements": 2,
               "resultats": [{"ref": "a", "resultat": SORTIE}, {"ref": "b", "erreur": {"code": "sortie_invalide"}}]}),
    ]
    c = client(service)
    lot = c.lot("charge.bilan", [{"ref": "a", "entree": {}}, {"ref": "b", "entree": {}}])
    assert lot.en_cours and not lot.termine and lot.elements == 2
    lot = c.etat_lot("l1")
    assert lot.termine and lot.par_ref()["a"]["resultat"] == SORTIE
    assert service["appels"][0]["corps"]["tache"] == "charge.bilan"
    assert service["appels"][1]["methode"] == "GET" and service["appels"][1]["chemin"] == "/v1/lots/l1"


def test_taches_et_usage(service):
    service["reponses"] = [(200, {"taches": [{"nom": "charge.seance"}]}), (200, {"mois": "2026-10"})]
    c = client(service)
    assert c.taches() == [{"nom": "charge.seance"}]
    assert c.usage("2026-10") == {"mois": "2026-10"}
    assert service["appels"][1]["chemin"] == "/v1/usage?mois=2026-10"


def test_client_factice():
    f = client_ia("factice", None)
    assert isinstance(f, ClientFactice) and f.configured
    with pytest.raises(TacheInconnue):
        f.tache("charge.seance", {})
    f.repondre("charge.seance", SORTIE)
    r = f.tache("charge.seance", {"texte": "footing"}, utilisateur="gabriel")
    assert r.resultat == SORTIE and f.appels[-1] == ("charge.seance", {"texte": "footing"}, "gabriel")
    r.resultat["discipline"] = "modifiée"
    assert f.tache("charge.seance", {}).resultat == SORTIE  # chaque réponse est une copie

    f.repondre("charge.bilan", lambda e: {"titre": f"Semaine de {e['qui']}"})
    lot = f.lot("charge.bilan", [{"ref": "g", "entree": {"qui": "Gabriel"}}])
    assert lot.termine and f.etat_lot(lot.id).par_ref()["g"]["resultat"] == {"titre": "Semaine de Gabriel"}

    f.repondre("charge.seance", BudgetAtteint("budget atteint", 429, "budget_atteint"))
    with pytest.raises(BudgetAtteint):
        f.tache("charge.seance", {})
    lot = f.lot("charge.seance", [{"ref": "x", "entree": {}}])
    assert lot.statut == "echoue" and lot.par_ref()["x"]["erreur"]["code"] == "budget_atteint"
