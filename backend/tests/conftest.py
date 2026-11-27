"""Test setup: each test gets a fresh, empty database.

By default tests use an in-memory SQLite DB so `make test` works without Docker.
To run against Postgres instead:
  TEST_DATABASE_URL=postgresql+psycopg://payledger:payledger@localhost:5432/payledger make test
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db import Base, get_session
from app.main import app
from app.seed import DEFAULT_ACCOUNTS
from app.models import Account

TEST_URL = os.getenv("TEST_DATABASE_URL", "sqlite://")


@pytest.fixture()
def session():
    kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool} \
        if TEST_URL.startswith("sqlite") else {}
    engine = create_engine(TEST_URL, **kwargs)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as s:
        for code, name, type_ in DEFAULT_ACCOUNTS:
            s.add(Account(code=code, name=name, type=type_.value))
        s.commit()
        yield s
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()
