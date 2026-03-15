from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app


def test_register_login_and_create_link_flow():
    init_db()
    with TestClient(app) as client:
        register = client.post(
            "/auth/register",
            json={"username": "bob", "email": "bob@example.com", "password": "secret123"},
        )
        assert register.status_code == 201
        token = register.json()["access_token"]

        create = client.post(
            "/links/shorten",
            json={"original_url": "https://example.com", "custom_alias": "bob-link"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create.status_code == 201
        assert create.json()["short_code"] == "bob-link"

        stats = client.get("/links/bob-link/stats")
        assert stats.status_code == 200
        assert stats.json()["original_url"] == "https://example.com"
