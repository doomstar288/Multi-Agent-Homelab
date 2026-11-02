from dataclasses import replace

from .conftest import AUTH, client_for


def test_authenticated_user(client):
    r = client.get("/api/me", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"name": "matt", "groups": ["admins", "users"], "email": "matt@example.com"}


def test_username_is_case_insensitive(client):
    assert client.get("/api/me", headers={**AUTH, "Remote-User": "Matt"}).status_code == 200


def test_missing_identity_header_is_refused(client):
    assert client.get("/api/me").status_code == 403


def test_unknown_user_is_refused(client):
    assert client.get("/api/me", headers={**AUTH, "Remote-User": "mallory"}).status_code == 403


def test_spoofed_headers_from_untrusted_peer_are_refused(settings):
    c = client_for(settings, host="172.30.0.99")
    assert c.get("/api/me", headers=AUTH).status_code == 403


def test_empty_config_refuses_everyone(settings):
    c = client_for(replace(settings, allowed_users=frozenset(), trusted_proxies=[]))
    assert c.get("/api/me", headers=AUTH).status_code == 403


def test_required_group(settings):
    c = client_for(replace(settings, required_group="homelab-admins"))
    assert c.get("/api/me", headers=AUTH).status_code == 403
    ok = c.get("/api/me", headers={**AUTH, "Remote-Groups": "homelab-admins"})
    assert ok.status_code == 200


def test_dashboard_requires_auth(client):
    assert client.get("/").status_code == 403
    r = client.get("/", headers=AUTH)
    assert r.status_code == 200
    assert "Signed in as <strong>matt</strong>" in r.text


def test_dashboard_escapes_username(settings):
    c = client_for(replace(settings, allowed_users=frozenset({"<b>x</b>"})))
    r = c.get("/", headers={**AUTH, "Remote-User": "<b>x</b>"})
    assert "<b>x</b>" not in r.text and "&lt;b&gt;" in r.text


def test_healthz_only_from_localhost(settings):
    assert client_for(settings).get("/healthz").status_code == 404
    assert client_for(settings, host="127.0.0.1").get("/healthz").json() == {"status": "ok"}


def test_no_api_docs(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path, headers=AUTH).status_code == 404


def test_security_headers(client):
    r = client.get("/api/me", headers=AUTH)
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


AUTHENTIK = {
    "X-authentik-username": "akadmin",
    "X-authentik-groups": "authentik Admins|homelab",
    "X-authentik-email": "a@example.com",
}


def authentik_client(settings, **overrides):
    s = replace(
        settings,
        allowed_users=frozenset({"akadmin"}),
        user_header="X-authentik-username",
        groups_header="X-authentik-groups",
        email_header="X-authentik-email",
        **overrides,
    )
    return client_for(s)


def test_authentik_headers(settings):
    r = authentik_client(settings).get("/api/me", headers=AUTHENTIK)
    assert r.status_code == 200
    assert r.json() == {"name": "akadmin", "groups": ["authentik Admins", "homelab"], "email": "a@example.com"}


def test_authentik_mode_ignores_remote_user(settings):
    # With Authentik, Remote-User is never set by the proxy, so a browser could
    # forge it. It must not be accepted.
    c = authentik_client(settings)
    assert c.get("/api/me", headers={"Remote-User": "akadmin"}).status_code == 403


def test_authentik_required_group_with_pipes(settings):
    c = authentik_client(settings, required_group="homelab")
    assert c.get("/api/me", headers=AUTHENTIK).status_code == 200
    assert c.get("/api/me", headers={**AUTHENTIK, "X-authentik-groups": "other"}).status_code == 403


def test_header_settings_from_env(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("HARNESS_USER_HEADER", "X-authentik-username")
    monkeypatch.delenv("HARNESS_GROUPS_HEADER", raising=False)
    s = Settings.from_env()
    assert s.user_header == "X-authentik-username"
    assert s.groups_header == "Remote-Groups"
