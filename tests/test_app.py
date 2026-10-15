import pytest

from app import app


@pytest.fixture
def client(monkeypatch):
    # Start every test from a clean environment so results do not depend on the host machine.
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("APP_VERSION", raising=False)
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client


def failed_checks(payload):
    return {check["name"] for check in payload["checks"] if not check["passed"]}


# --- GET / -------------------------------------------------------------------

def test_dashboard_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    body = response.get_data(as_text=True)
    assert "ReleaseGuard" in body
    assert "/health" in body and "/release" in body


def test_dashboard_shows_configured_release(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("APP_VERSION", "2.3.4")
    body = client.get("/").get_data(as_text=True)
    assert "2.3.4" in body
    assert "staging" in body
    assert "READY" in body and "NOT READY" not in body


def test_dashboard_escapes_untrusted_values(client, monkeypatch):
    monkeypatch.setenv("APP_VERSION", "<script>alert(1)</script>")
    body = client.get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body


# --- GET /health ---------------------------------------------------------------

def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["service"] == "ReleaseGuard"
    assert "timestamp" in payload


# --- GET /release ---------------------------------------------------------------

def test_release_uses_safe_defaults(client):
    response = client.get("/release")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["application"] == "ReleaseGuard"
    assert payload["environment"] == "development"
    assert payload["version"] == "0.0.0-dev"
    assert payload["release_ready"] is True


def test_release_reads_environment_variables(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "Production")
    monkeypatch.setenv("APP_VERSION", "1.4.2")
    payload = client.get("/release").get_json()
    assert payload["environment"] == "production"
    assert payload["version"] == "1.4.2"
    assert payload["release_ready"] is True
    assert failed_checks(payload) == set()


def test_blank_variables_fall_back_to_defaults(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "   ")
    monkeypatch.setenv("APP_VERSION", "")
    payload = client.get("/release").get_json()
    assert payload["environment"] == "development"
    assert payload["version"] == "0.0.0-dev"


def test_release_not_ready_for_unknown_environment(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "qa-sandbox")
    monkeypatch.setenv("APP_VERSION", "1.0.0")
    payload = client.get("/release").get_json()
    assert payload["release_ready"] is False
    assert failed_checks(payload) == {"environment_is_known"}


def test_release_not_ready_for_invalid_version(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("APP_VERSION", "latest")
    payload = client.get("/release").get_json()
    assert payload["release_ready"] is False
    assert failed_checks(payload) == {"version_is_semantic"}


def test_release_not_ready_for_prerelease_in_production(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_VERSION", "1.5.0-rc.1")
    payload = client.get("/release").get_json()
    assert payload["release_ready"] is False
    assert failed_checks(payload) == {"production_uses_stable_version"}


def test_prerelease_allowed_in_staging(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("APP_VERSION", "1.5.0-rc.1")
    assert client.get("/release").get_json()["release_ready"] is True


# --- Error handling ---------------------------------------------------------------

def test_unknown_route_returns_json_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["status"] == 404


def test_wrong_method_returns_json_405(client):
    response = client.post("/release")
    assert response.status_code == 405
    assert response.get_json()["status"] == 405
