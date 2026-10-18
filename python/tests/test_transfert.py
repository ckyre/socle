import os
import uuid
from datetime import date, datetime, time
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Table,
    Time,
    Uuid,
    create_engine,
    insert,
    select,
)

from socle import transfert

TOKEN = "t" * 40


def schema():
    md = MetaData()
    chapters = Table(
        "chapters", md,
        Column("id", Integer, primary_key=True),
        Column("parent_id", Integer, ForeignKey("chapters.id")),
        Column("title", String(50)),
    )
    entries = Table(
        "user", md,  # nom réservé en PostgreSQL : vérifie la mise entre guillemets
        Column("id", Integer, primary_key=True),
        Column("chapter_id", Integer, ForeignKey("chapters.id")),
        Column("amount", Numeric(10, 2)),
        Column("ratio", Numeric(5, 2, asdecimal=False)),
        Column("at", DateTime),
        Column("day", Date),
        Column("hour", Time),
        Column("blob", LargeBinary),
        Column("ref", Uuid),
    )
    tokens = Table("tokens", md, Column("key", String(10), primary_key=True), Column("n", Integer))
    return md, chapters, entries


def engines():
    out = [("sqlite", lambda tmp: create_engine(f"sqlite:///{tmp}/a.db"), lambda tmp: create_engine(f"sqlite:///{tmp}/b.db"))]
    pg = os.environ.get("TEST_PG_URL")
    if pg:
        def make(name):
            def f(_tmp):
                admin = create_engine(pg, isolation_level="AUTOCOMMIT")
                with admin.connect() as c:
                    c.exec_driver_sql(f"DROP DATABASE IF EXISTS {name}")
                    c.exec_driver_sql(f"CREATE DATABASE {name}")
                admin.dispose()
                return create_engine(pg.rsplit("/", 1)[0] + "/" + name if "?" not in pg
                                     else pg.replace("/postgres?", f"/{name}?"))
            return f
        out.append(("postgresql", make("socle_src"), make("socle_dst")))
    return out


@pytest.mark.parametrize("kind,src_factory,dst_factory", engines(), ids=[e[0] for e in engines()])
def test_roundtrip_preserves_everything(tmp_path, kind, src_factory, dst_factory):
    md, chapters, entries = schema()
    src, dst = src_factory(tmp_path), dst_factory(tmp_path)
    md.create_all(src)
    md.create_all(dst)
    ref = uuid.uuid4()
    with src.begin() as c:
        # L'enfant (id 1) pointe vers un parent créé après lui (id 2).
        c.execute(insert(chapters), [{"id": 2, "parent_id": None, "title": "Parent"}])
        c.execute(insert(chapters), [{"id": 1, "parent_id": 2, "title": "Enfant"}])
        c.execute(insert(entries), [{
            "id": 7, "chapter_id": 1, "amount": Decimal("12.34"), "ratio": 0.5, "at": datetime(2026, 10, 18, 17, 30, 5),
            "day": date(2026, 10, 18), "hour": time(8, 15), "blob": b"\x00\x01\xff", "ref": ref,
        }])
        c.execute(insert(md.tables["tokens"]), [{"key": "abc", "n": 3}])

    tables = list(md.sorted_tables)
    data = transfert.export_data(src, tables)
    import json
    data = json.loads(json.dumps(data))  # passe vraiment par JSON
    counts = transfert.import_data(dst, tables, data)
    assert counts == {"chapters": 2, "user": 1, "tokens": 1}

    with src.connect() as a, dst.connect() as b:
        for t in tables:
            order = list(t.primary_key.columns)
            assert a.execute(select(t).order_by(*order)).all() == b.execute(select(t).order_by(*order)).all()

    # Séquences recalées : une nouvelle ligne ne réutilise pas un identifiant importé.
    with dst.begin() as c:
        new_id = c.execute(insert(entries).values(chapter_id=2).returning(entries.c.id)).scalar()
    assert new_id > 7

    # Une base non vide n'est jamais modifiée.
    with pytest.raises(RuntimeError, match="n'est pas vide"):
        transfert.import_data(dst, tables, data)


def test_import_refuses_unknown_tables_and_rolls_back(tmp_path):
    md, chapters, entries = schema()
    eng = create_engine(f"sqlite:///{tmp_path}/c.db")
    md.create_all(eng)
    tables = list(md.sorted_tables)
    with pytest.raises(ValueError):
        transfert.import_data(eng, tables, {"inconnue": []})
    # Ligne invalide (clé en double) : tout est annulé.
    bad = {"chapters": [{"id": 1, "parent_id": None, "title": "A"}, {"id": 1, "parent_id": None, "title": "B"}]}
    with pytest.raises(Exception):
        transfert.import_data(eng, tables, bad)
    assert transfert.is_empty(eng, tables)


def test_export_router_requires_token(tmp_path):
    md, chapters, _ = schema()
    eng = create_engine(f"sqlite:///{tmp_path}/d.db")
    md.create_all(eng)
    tables = list(md.sorted_tables)
    current = {"token": None}
    app = FastAPI()
    app.include_router(transfert.export_router(eng, tables, lambda: current["token"]))
    c = TestClient(app)
    path = transfert.EXPORT_PATH
    assert c.get(path, headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 404  # non configuré
    current["token"] = "court"
    assert c.get(path, headers={"Authorization": "Bearer court"}).status_code == 404     # jeton trop faible
    current["token"] = TOKEN
    assert c.get(path).status_code == 404
    assert c.get(path, headers={"Authorization": f"Basic {TOKEN}"}).status_code == 404
    assert c.get(path, headers={"Authorization": f"Bearer {TOKEN}x"}).status_code == 404
    r = c.get(path, headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200 and set(r.json()) == {"chapters", "user", "tokens"}


def test_import_from_checks_its_inputs(tmp_path):
    md, *_ = schema()
    eng = create_engine(f"sqlite:///{tmp_path}/e.db")
    md.create_all(eng)
    tables = list(md.sorted_tables)
    with pytest.raises(ValueError, match="https"):
        transfert.import_from("http://exemple.fr/x", TOKEN, eng, tables)
    with pytest.raises(ValueError, match="32"):
        transfert.import_from("https://exemple.fr/x", "court", eng, tables)
    with eng.begin() as c:
        c.execute(insert(md.tables["tokens"]), [{"key": "a", "n": 1}])
    # Base non vide : rien n'est téléchargé.
    assert transfert.import_from("https://exemple.invalid/x", TOKEN, eng, tables) is None
