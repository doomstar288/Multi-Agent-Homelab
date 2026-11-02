import ipaddress

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PROXY_IP = "172.30.0.2"
AUTH = {"Remote-User": "matt", "Remote-Groups": "admins,users", "Remote-Email": "matt@example.com"}


@pytest.fixture
def settings(tmp_path):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "claude_api_key").write_text("sk-test\n")
    (secrets / "gemini_api_key").write_text("")  # empty means not configured
    return Settings(
        allowed_users=frozenset({"matt"}),
        trusted_proxies=[ipaddress.ip_network(f"{PROXY_IP}/32")],
        db_path=tmp_path / "harness.db",
        secrets_dir=secrets,
    )


def client_for(settings, host=PROXY_IP):
    return TestClient(create_app(settings), client=(host, 50000))


@pytest.fixture
def client(settings):
    return client_for(settings)
