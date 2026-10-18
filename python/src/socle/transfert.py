"""Transfert des données d'un déploiement à un autre (migration d'une base vers une autre).

Rien n'est actif par défaut : une application ne branche ce module que le temps d'une migration.

Source      : `export_router(...)` ajoute GET /api/transfer/export, protégé par un jeton dédié (32 caractères
              minimum, en-tête Authorization: Bearer). Sans jeton configuré, la route répond 404. Comme la
              passerelle retire l'en-tête Authorization, la destination appelle la source directement.
Destination : `import_from(url, token, engine, tables)` télécharge l'export et l'insère dans une seule
              transaction, uniquement si toutes les tables sont vides. En cas d'échec, l'exception remonte :
              l'application ne démarre pas, on ne repart jamais d'une base vide par erreur.

Le format est du JSON : {table: [lignes]}, identifiants compris. Les types non JSON (dates, décimaux, binaires,
UUID) sont encodés en texte et décodés selon le type de la colonne de destination.
"""


import base64
import hmac
import logging
import uuid
from collections.abc import Callable, Sequence
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, LargeBinary, Numeric, Table, Time, Uuid, func, select, text
from sqlalchemy.engine import Engine

log = logging.getLogger("socle.transfert")
MIN_TOKEN_LENGTH = 32
EXPORT_PATH = "/api/transfer/export"


# --- Encodage ---------------------------------------------------------------------------------------------------


def _encode(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _decode(column, value):
    if value is None:
        return None
    t = column.type
    if isinstance(t, DateTime):
        return datetime.fromisoformat(value)
    if isinstance(t, Date):
        return date.fromisoformat(value)
    if isinstance(t, Time):
        return time.fromisoformat(value)
    if isinstance(t, LargeBinary):
        return base64.b64decode(value)
    if isinstance(t, Uuid) and isinstance(value, str):
        return uuid.UUID(value) if t.as_uuid else value
    if isinstance(t, Numeric) and t.asdecimal and isinstance(value, str):
        return Decimal(value)
    return value


def _self_refs(table: Table) -> list[str]:
    """Colonnes qui pointent vers la même table (ex. chapters.parent_id) : rétablies après coup."""
    return [fk.parent.name for fk in table.foreign_keys if fk.column.table is table]


# --- Export -----------------------------------------------------------------------------------------------------


def export_data(engine: Engine, tables: Sequence[Table]) -> dict[str, list[dict]]:
    """Toutes les lignes des tables données, dans l'ordre de leur clé primaire."""
    with engine.connect() as con:
        return {
            t.name: [{k: _encode(v) for k, v in row.items()}
                     for row in con.execute(select(t).order_by(*t.primary_key.columns)).mappings()]
            for t in tables
        }


def check_token(given: str, expected: str | None) -> bool:
    """Jeton d'export valide ? Un jeton configuré trop court désactive l'export."""
    if not expected or len(expected) < MIN_TOKEN_LENGTH:
        return False
    return hmac.compare_digest(given.encode(), expected.encode())


def export_router(engine: Engine | Callable[[], Engine], tables: Sequence[Table] | Callable[[], Sequence[Table]],
                  token: str | Callable[[], str | None] | None, path: str = EXPORT_PATH):
    """Routeur FastAPI exposant l'export. Pensez à ajouter `path` aux chemins publics du GatewayMiddleware."""
    from fastapi import APIRouter, HTTPException, Request

    router = APIRouter()

    @router.get(path, include_in_schema=False)
    def export_endpoint(request: Request):
        expected = token() if callable(token) else token
        scheme, _, given = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not check_token(given.strip(), expected):
            raise HTTPException(404)
        eng = engine() if callable(engine) else engine
        data = export_data(eng, tables() if callable(tables) else tables)
        log.info("Export : %s", {k: len(v) for k, v in data.items()})
        return data

    return router


# --- Import -----------------------------------------------------------------------------------------------------


def import_data(engine: Engine, tables: Sequence[Table], data: dict[str, list[dict]]) -> dict[str, int]:
    """Insère `data` dans des tables vides, en une seule transaction (tout ou rien). Renvoie le nombre de lignes."""
    unknown = set(data) - {t.name for t in tables}
    if unknown:
        raise ValueError(f"Tables inconnues dans l'export : {sorted(unknown)}")
    counts: dict[str, int] = {}
    with engine.begin() as con:
        for t in tables:
            if con.execute(select(func.count()).select_from(t)).scalar():
                raise RuntimeError(f"La table {t.name} n'est pas vide : import refusé")
        for t in tables:  # ordre des dépendances (Metadata.sorted_tables)
            cols = {c.name: c for c in t.columns}
            rows = [{k: _decode(cols[k], v) for k, v in r.items() if k in cols} for r in data.get(t.name, [])]
            refs = _self_refs(t)
            pk = [c.name for c in t.primary_key.columns]
            if rows:
                con.execute(t.insert(), [{**r, **{c: None for c in refs}} for r in rows])
            for r in rows:  # un enfant peut précéder son parent : liens internes rétablis ensuite
                values = {c: r[c] for c in refs if r.get(c) is not None}
                if values:
                    con.execute(t.update().where(*[t.c[k] == r[k] for k in pk]).values(**values))
            counts[t.name] = len(rows)
        if con.dialect.name == "postgresql":  # identifiants copiés tels quels : on recale les séquences
            quote = con.dialect.identifier_preparer.quote
            for t in tables:
                for c in t.primary_key.columns:
                    if isinstance(c.type, Integer):
                        name = quote(t.name)
                        con.execute(
                            text(f"SELECT setval(pg_get_serial_sequence(:tbl, :col), "
                                 f"COALESCE((SELECT MAX({quote(c.name)}) FROM {name}), 0) + 1, false)"),
                            {"tbl": name, "col": c.name},
                        )
    return counts


def is_empty(engine: Engine, tables: Sequence[Table]) -> bool:
    with engine.connect() as con:
        return not any(con.execute(select(func.count()).select_from(t)).scalar() for t in tables)


def import_from(url: str, token: str, engine: Engine, tables: Sequence[Table], *, timeout: float = 120) -> dict | None:
    """Importe l'export de `url` si la base est vide. Renvoie les comptes, ou None si la base contenait déjà des données."""
    import httpx

    if not url.startswith("https://"):
        raise ValueError("L'URL d'import doit être en https")
    if len(token or "") < MIN_TOKEN_LENGTH:
        raise ValueError(f"Le jeton d'import doit faire au moins {MIN_TOKEN_LENGTH} caractères")
    if not is_empty(engine, tables):
        log.info("Import ignoré : la base contient déjà des données")
        return None
    r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=timeout, follow_redirects=False)
    if r.status_code != 200:
        raise RuntimeError(f"Import impossible : la source répond {r.status_code}")
    counts = import_data(engine, tables, r.json())
    log.info("Import terminé : %s", counts)
    return counts
