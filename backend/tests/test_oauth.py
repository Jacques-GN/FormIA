"""Tests OAuth Google et registre de « state » (réseau simulé)."""

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import GoogleError, MissingConfiguration
from app.integrations.google_forms import oauth, token_store


def configure_google(monkeypatch) -> None:
    monkeypatch.setattr(
        oauth,
        "settings",
        Settings(
            google_client_id="client-id",
            google_client_secret="client-secret",
            google_redirect_uri="http://127.0.0.1:8000/auth/google/callback",
        ),
    )


# --- token_store : le « state » est à usage unique et expire ---


def test_un_state_ne_sert_qu_une_fois():
    token_store.remember_state("state-1", "session-1")

    assert token_store.consume_state("state-1") == "session-1"
    assert token_store.consume_state("state-1") is None


def test_un_state_expire_est_refuse(monkeypatch):
    maintenant = {"valeur": 1000.0}
    monkeypatch.setattr(token_store.time, "monotonic", lambda: maintenant["valeur"])
    token_store.remember_state("state-1", "session-1")

    maintenant["valeur"] += token_store.STATE_LIFETIME_SECONDS + 1

    assert token_store.consume_state("state-1") is None


def test_le_jeton_expire_avec_une_marge(monkeypatch):
    maintenant = {"valeur": 1000.0}
    monkeypatch.setattr(token_store.time, "monotonic", lambda: maintenant["valeur"])
    token_store.store_token("session-1", "jeton", expires_in=3600)

    assert token_store.get_token("session-1") == "jeton"

    maintenant["valeur"] += 3600 - token_store.TOKEN_SAFETY_MARGIN_SECONDS
    assert token_store.get_token("session-1") is None


# --- URL de consentement ---


def test_build_authorization_url_contains_minimal_parameters(monkeypatch):
    configure_google(monkeypatch)

    url = oauth.build_authorization_url("state-abc")
    query = parse_qs(urlparse(url).query)

    assert url.startswith(oauth.AUTHORIZATION_URL)
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["http://127.0.0.1:8000/auth/google/callback"]
    assert query["response_type"] == ["code"]
    assert query["scope"] == [oauth.FORMS_SCOPE]
    assert query["state"] == ["state-abc"]


def test_build_authorization_url_requires_configuration(monkeypatch):
    monkeypatch.setattr(
        oauth,
        "settings",
        Settings(google_client_id="", google_redirect_uri=""),
    )

    with pytest.raises(MissingConfiguration):
        oauth.build_authorization_url("state-abc")


# --- échange du code ---


def test_exchange_code_returns_the_access_token(monkeypatch):
    configure_google(monkeypatch)
    envoye = {}

    def handle(request: httpx.Request) -> httpx.Response:
        envoye["body"] = request.content.decode()
        return httpx.Response(200, json={"access_token": "jeton", "expires_in": 3600})

    resultat = oauth.exchange_code_for_token(
        "code-1", transport=httpx.MockTransport(handle)
    )

    assert resultat == {"access_token": "jeton", "expires_in": 3600}
    assert "grant_type=authorization_code" in envoye["body"]
    assert "client-secret" in envoye["body"]  # envoyé au serveur, jamais au client


def test_exchange_code_translates_a_google_refusal(monkeypatch):
    configure_google(monkeypatch)

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    with pytest.raises(GoogleError) as erreur:
        oauth.exchange_code_for_token(
            "code-1", transport=httpx.MockTransport(handle)
        )

    assert "invalid_grant" not in erreur.value.message


def test_exchange_code_requires_configuration():
    with pytest.raises(MissingConfiguration):
        oauth.exchange_code_for_token("code-1")
