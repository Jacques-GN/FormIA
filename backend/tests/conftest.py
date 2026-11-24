"""Réglages communs à tous les tests."""

import pytest

from app.core.config import Settings
from app.integrations.google_forms import creation_store, oauth, token_store
from app.services import LLM


@pytest.fixture(autouse=True)
def jamais_de_vrai_fournisseur(monkeypatch):
    """Empêche tout test d'appeler le vrai fournisseur LLM ou Google.

    Settings() lit le vrai fichier .env. Avec des valeurs vides imposées,
    LLM.generate_completion et oauth lèvent une erreur de configuration avant
    tout appel réseau. Un test qui a besoin d'une configuration la remplace
    lui-même, avec un transport httpx simulé.
    """
    monkeypatch.setattr(
        LLM, "settings", Settings(llm_api_key="", llm_model="", llm_base_url="")
    )
    monkeypatch.setattr(
        oauth,
        "settings",
        Settings(
            google_client_id="",
            google_client_secret="",
            google_redirect_uri="",
        ),
    )


@pytest.fixture(autouse=True)
def registres_isoles():
    """Chaque test part d'un registre OAuth et d'un suivi de création vides."""
    token_store.clear_all()
    creation_store.clear_all()
    yield
    token_store.clear_all()
    creation_store.clear_all()
