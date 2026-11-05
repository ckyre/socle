"""Client du service IA (accès mutualisé à l'API Claude). Bibliothèque standard seulement, appelable depuis un fil.

    from socle.ia import BudgetAtteint, ErreurIA, client_ia

    ia = client_ia(settings.ia_url, settings.ia_key)   # <PREFIXE>IA_URL, <PREFIXE>IA_KEY
    if ia.configured:
        r = ia.tache("charge.seance", {"texte": texte, "date": "2026-11-05", "disciplines": [...]},
                     utilisateur=portal_username(sub))
        r.resultat   # dict validé par le schéma de sortie de la tâche : une suggestion à faire valider

L'appel est bloquant (jusqu'à 65 s) : depuis FastAPI, l'appeler dans une route `def` (exécutée dans un fil), pas
`async def`. Chaque erreur a sa classe (`BudgetAtteint`, `SortieInvalide`, `Indisponible`…) ; une fonction IA garde
toujours un chemin manuel, et une erreur masque le bouton au lieu de bloquer l'écran.

Lots (moitié prix, résultat en moins de 24 h) :

    lot = ia.lot("charge.bilan", [{"ref": "gabriel-2026-W45", "entree": {...}, "utilisateur": "gabriel"}])
    … plus tard (tâche Periodic) :
    lot = ia.etat_lot(lot.id)
    if lot.termine:
        for ref, element in lot.par_ref().items(): element.get("resultat") ou element["erreur"]

Tests et développement : `client_ia("factice", None)` (ou `ClientFactice()`) répond sans réseau, avec les réponses
préparées par le test : `factice.repondre("charge.seance", {...})`.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

FACTICE = "factice"


# --- Erreurs ----------------------------------------------------------------------------------------------


class ErreurIA(Exception):
    """Erreur du service IA. `code` : celui du service (`budget_atteint`…) ; `permanent` : inutile de réessayer tel
    quel (requête à corriger, clé refusée)."""

    def __init__(self, message: str, status: int | None = None, code: str = "erreur", details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.details = details or {}

    @property
    def permanent(self) -> bool:
        return self.status in (400, 401, 403, 404, 413)


class EntreeInvalide(ErreurIA):
    """400 : entrée hors schéma ; `details["champs"]` liste les champs en cause."""


class CleRefusee(ErreurIA):
    """401 ou 403 : clé de l'application inconnue, ou tâche d'une autre application."""


class TacheInconnue(ErreurIA):
    """404 : tâche (ou lot) inconnue du service."""


class EntreeTropLongue(ErreurIA):
    """413 : entrée au-delà de la limite de la tâche : tronquer ou découper."""


class SortieInvalide(ErreurIA):
    """422 : réponse du modèle inutilisable (hors schéma après une relance, tronquée, refusée) : proposer de réessayer."""


class BudgetAtteint(ErreurIA):
    """429 : budget mensuel de l'application (ou de la suite) atteint : masquer la fonction jusqu'au mois suivant."""


class TropDeRequetes(ErreurIA):
    """429 : trop d'appels cette minute ou ce jour."""


class Indisponible(ErreurIA):
    """502, 503, 504 ou service injoignable : réessayer plus tard."""


_PAR_CODE: dict[str, type[ErreurIA]] = {
    "entree_invalide": EntreeInvalide,
    "cle_invalide": CleRefusee,
    "tache_interdite": CleRefusee,
    "tache_inconnue": TacheInconnue,
    "lot_inconnu": TacheInconnue,
    "entree_trop_longue": EntreeTropLongue,
    "sortie_invalide": SortieInvalide,
    "budget_atteint": BudgetAtteint,
    "trop_de_requetes": TropDeRequetes,
    "anthropic_indisponible": Indisponible,
    "anthropic_erreur": Indisponible,
    "delai_depasse": Indisponible,
}
_PAR_STATUT: dict[int, type[ErreurIA]] = {400: EntreeInvalide, 401: CleRefusee, 403: CleRefusee, 404: TacheInconnue,
                                         413: EntreeTropLongue, 422: SortieInvalide, 429: TropDeRequetes}


def _erreur(status: int, corps: Any) -> ErreurIA:
    erreur = corps.get("erreur") if isinstance(corps, dict) else None
    if not isinstance(erreur, dict):
        erreur = {}
    code = str(erreur.get("code") or "erreur")
    message = str(erreur.get("message") or f"service IA : erreur {status}")
    details = {k: v for k, v in erreur.items() if k not in ("code", "message")}
    classe = _PAR_CODE.get(code) or _PAR_STATUT.get(status) or (Indisponible if status >= 500 else ErreurIA)
    return classe(message, status, code, details)


# --- Résultats --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Resultat:
    """Réponse d'une tâche. `resultat` : la sortie validée ; `usage` : modèle, tokens, coût en dollars."""

    id: str
    tache: str
    version: int
    resultat: dict
    usage: dict = field(default_factory=dict)
    duree_ms: int = 0

    @classmethod
    def depuis(cls, d: dict) -> Resultat:
        return cls(id=str(d.get("id", "")), tache=d.get("tache", ""), version=int(d.get("version", 0)),
                   resultat=d.get("resultat") or {}, usage=d.get("usage") or {}, duree_ms=int(d.get("duree_ms", 0)))


@dataclass(frozen=True)
class Lot:
    """État d'un lot. `resultats` (une fois terminé) : [{"ref", "resultat"} ou {"ref", "erreur": {"code", …}}]."""

    id: str
    tache: str
    statut: str  # en_cours, termine, echoue
    elements: int = 0
    resultats: list[dict] | None = None

    @property
    def en_cours(self) -> bool:
        return self.statut == "en_cours"

    @property
    def termine(self) -> bool:
        return self.statut in ("termine", "echoue")

    def par_ref(self) -> dict[str, dict]:
        return {r["ref"]: r for r in self.resultats or []}

    @classmethod
    def depuis(cls, d: dict) -> Lot:
        return cls(id=str(d.get("id", "")), tache=d.get("tache", ""), statut=d.get("statut", ""),
                   elements=int(d.get("elements", 0)), resultats=d.get("resultats"))


# --- Client -----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ClientIA:
    """Client du service IA (POST /v1/taches/<tâche>, clé de l'application)."""

    url: str | None
    key: str | None
    timeout: float = 65.0  # le service attend l'API Claude 60 s au plus
    pause_reprise: float = 1.0

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key)

    def tache(self, nom: str, entree: Any, utilisateur: str | None = None,
              cle_idempotence: str | None = None) -> Resultat:
        """Exécute une tâche. Une seule reprise si le service est momentanément indisponible ; la clé d'idempotence
        (générée si absente) garantit que la reprise n'est pas facturée deux fois."""
        corps: dict = {"entree": entree}
        if utilisateur:
            corps["utilisateur"] = utilisateur
        entetes = {"Idempotency-Key": cle_idempotence or uuid.uuid4().hex}
        chemin = "/v1/taches/" + urllib.parse.quote(nom, safe=".")
        try:
            return Resultat.depuis(self._requete("POST", chemin, corps, entetes))
        except Indisponible as e:
            if e.code == "delai_depasse" or e.status == 504:
                raise  # l'appel a peut-être abouti côté API : ne pas le relancer à l'aveugle
            time.sleep(self.pause_reprise)
            return Resultat.depuis(self._requete("POST", chemin, corps, entetes))

    def lot(self, nom: str, elements: Iterable[dict]) -> Lot:
        """Dépose un lot : éléments {"ref", "entree", "utilisateur"?}, 100 au plus, `ref` unique."""
        return Lot.depuis(self._requete("POST", "/v1/lots", {"tache": nom, "elements": list(elements)}))

    def etat_lot(self, lot_id: str) -> Lot:
        return Lot.depuis(self._requete("GET", "/v1/lots/" + urllib.parse.quote(lot_id, safe="")))

    def taches(self) -> list[dict]:
        """Tâches de l'application : version, modèle, schémas d'entrée et de sortie, exemples."""
        return self._requete("GET", "/v1/taches").get("taches", [])

    def usage(self, mois: str | None = None) -> dict:
        """Dépense du mois (AAAA-MM, par défaut le mois en cours) et budget restant."""
        return self._requete("GET", "/v1/usage" + (f"?mois={urllib.parse.quote(mois)}" if mois else ""))

    def _requete(self, methode: str, chemin: str, corps: dict | None = None, entetes: dict | None = None) -> dict:
        if not self.configured:
            raise ErreurIA("service IA non configuré (URL et clé)")
        requete = urllib.request.Request(
            self.url.rstrip("/") + chemin,  # type: ignore[union-attr]
            data=json.dumps(corps).encode() if corps is not None else None,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json", **(entetes or {})},
            method=methode,
        )
        try:
            with urllib.request.urlopen(requete, timeout=self.timeout) as r:  # noqa: S310 (adresse de la configuration)
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                corps_erreur = json.loads(e.read() or b"{}")
            except ValueError:
                corps_erreur = {}
            raise _erreur(e.code, corps_erreur) from e
        except TimeoutError as e:
            raise Indisponible("service IA : délai dépassé", None, "delai_depasse") from e
        except (urllib.error.URLError, OSError) as e:
            raise Indisponible(f"service IA injoignable ({e.__class__.__name__})", None, "injoignable") from e


# --- Client factice (tests, développement local) ---------------------------------------------------------

Reponse = dict | Callable[[Any], dict] | ErreurIA


class ClientFactice:
    """Répond sans réseau, avec les réponses préparées : une sortie (dict), une fonction de l'entrée, ou une
    exception à lever. Garde les appels reçus dans `appels` : [(tâche, entrée, utilisateur)]."""

    configured = True

    def __init__(self, reponses: dict[str, Reponse] | None = None):
        self.reponses: dict[str, Reponse] = dict(reponses or {})
        self.appels: list[tuple[str, Any, str | None]] = []
        self._lots: dict[str, Lot] = {}

    def repondre(self, nom: str, reponse: Reponse) -> None:
        self.reponses[nom] = reponse

    def _sortie(self, nom: str, entree: Any) -> dict:
        if nom not in self.reponses:
            raise TacheInconnue(f"client factice : aucune réponse préparée pour « {nom} »", 404, "tache_inconnue")
        reponse = self.reponses[nom]
        if isinstance(reponse, ErreurIA):
            raise reponse
        return reponse(entree) if callable(reponse) else json.loads(json.dumps(reponse))

    def tache(self, nom: str, entree: Any, utilisateur: str | None = None,
              cle_idempotence: str | None = None) -> Resultat:
        self.appels.append((nom, entree, utilisateur))
        return Resultat(id=uuid.uuid4().hex, tache=nom, version=0, resultat=self._sortie(nom, entree),
                        usage={"modele": FACTICE, "entree": 0, "sortie": 0, "cout_usd": 0.0})

    def lot(self, nom: str, elements: Iterable[dict]) -> Lot:
        """Le lot est terminé tout de suite."""
        resultats = []
        for e in elements:
            self.appels.append((nom, e["entree"], e.get("utilisateur")))
            try:
                resultats.append({"ref": e["ref"], "resultat": self._sortie(nom, e["entree"])})
            except ErreurIA as err:
                resultats.append({"ref": e["ref"], "erreur": {"code": err.code, "message": err.message}})
        statut = "termine" if any("resultat" in r for r in resultats) else "echoue"
        lot = Lot(id=uuid.uuid4().hex, tache=nom, statut=statut, elements=len(resultats), resultats=resultats)
        self._lots[lot.id] = lot
        return lot

    def etat_lot(self, lot_id: str) -> Lot:
        if lot_id not in self._lots:
            raise TacheInconnue("lot inconnu", 404, "lot_inconnu")
        return self._lots[lot_id]

    def taches(self) -> list[dict]:
        return [{"nom": n} for n in sorted(self.reponses)]

    def usage(self, mois: str | None = None) -> dict:
        return {"mois": mois, "depense_usd": 0.0, "par_tache": []}


def client_ia(url: str | None, key: str | None, timeout: float = 65.0) -> ClientIA | ClientFactice:
    """Le client de la configuration : `<PREFIXE>IA_URL=factice` donne un client factice (sans réponses préparées)."""
    if (url or "").strip() == FACTICE:
        return ClientFactice()
    return ClientIA(url or None, key or None, timeout)
