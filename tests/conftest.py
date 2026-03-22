from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

from app import database, main
from app.cache import cache
from app.models import AppConfig, User


@pytest.fixture()
def test_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / 'test.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )

    monkeypatch.setattr(database, 'engine', engine)
    monkeypatch.setattr(main, 'engine', engine)

    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    cache._storage.clear()


@pytest.fixture()
def session(test_engine) -> Generator[Session, None, None]:
    with Session(test_engine) as session:
        yield session


@pytest.fixture()
def client(test_engine) -> Generator[TestClient, None, None]:
    with TestClient(main.app) as client:
        yield client


@pytest.fixture()
def registered_user(client):
    payload = {
        'username': 'alice',
        'email': 'alice@example.com',
        'password': 'secret123',
    }
    response = client.post('/auth/register', json=payload)
    assert response.status_code == 201
    token = response.json()['access_token']
    return payload, token


@pytest.fixture()
def auth_headers(registered_user):
    _, token = registered_user
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture()
def second_user(client):
    payload = {
        'username': 'bob',
        'email': 'bob@example.com',
        'password': 'secret123',
    }
    response = client.post('/auth/register', json=payload)
    assert response.status_code == 201
    token = response.json()['access_token']
    return payload, token


@pytest.fixture()
def second_auth_headers(second_user):
    _, token = second_user
    return {'Authorization': f'Bearer {token}'}
