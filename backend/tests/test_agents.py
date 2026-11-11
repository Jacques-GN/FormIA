"""Tests du graphe d'orchestration des demandes de formulaires."""

import pytest
from pydantic import BaseModel

from app.agents import nodes
from app.agents.orchestrator import orchestrate_form_request
from app.schemas.form import Form, Question, QuestionType


def test_orchestrator_validates_and_runs_generation(monkeypatch):
    expected_form = Form(
        title="Inscription",
        questions=[Question(title="Nom", type=QuestionType.SHORT_TEXT)],
    )
    received_prompts = []

    def fake_generate_form(prompt: str) -> Form:
        received_prompts.append(prompt)
        return expected_form

    monkeypatch.setattr(nodes, "generate_form_from_prompt", fake_generate_form)

    result = orchestrate_form_request("  Créer un formulaire d'inscription  ")

    assert result == expected_form
    assert received_prompts == ["Créer un formulaire d'inscription"]


def test_orchestrator_rejects_an_empty_request(monkeypatch):
    def generation_must_not_run(prompt: str) -> BaseModel:
        pytest.fail("La génération ne doit pas être appelée pour une demande vide.")

    monkeypatch.setattr(nodes, "generate_form_from_prompt", generation_must_not_run)

    with pytest.raises(ValueError, match="ne peut pas être vide"):
        orchestrate_form_request("   ")
