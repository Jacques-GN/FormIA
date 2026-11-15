"""Réglages communs à tous les tests."""

import pytest

from app.core.config import Settings
from app.services import LLM


@pytest.fixture(autouse=True)
def jamais_de_vrai_fournisseur(monkeypatch):
    """Empêche tout test d'appeler le vrai fournisseur LLM.

    Settings() lit le vrai fichier .env. Avec des valeurs vides imposées,
    LLM.generate_completion lève une RuntimeError avant tout appel réseau.
    Un test qui a besoin d'une configuration la remplace lui-même.
    """
    monkeypatch.setattr(
        LLM, "settings", Settings(llm_api_key="", llm_model="", llm_base_url="")
    )