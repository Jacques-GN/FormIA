"""Tests de l'adaptateur LLM et de la logique IA (form_generator)."""

import json

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.form import QuestionType
from app.services import LLM, form_generator

MESSAGES = [{"role": "user", "content": "Créer un formulaire d'inscription"}]

FORMULAIRE_JSON = json.dumps(
    {
        "title": "Inscription",
        "description": "",
        "questions": [
            {
                "title": "Nom complet",
                "type": "short_text",
                "required": True,
                "options": [],
            }
        ],
    }
)


def configured_settings() -> Settings:
    return Settings(
        llm_api_key="test-api-key",
        llm_model="test-model",
        llm_base_url="https://llm.example/v1",
    )


# --- LLM.py ---


def test_generate_completion_sends_compatible_request(monkeypatch):
    monkeypatch.setattr(LLM, "settings", configured_settings())
    request_data = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        request_data["url"] = str(request.url)
        request_data["authorization"] = request.headers["Authorization"]
        request_data["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"title": "Inscription"}'}}]},
        )

    result = LLM.generate_completion(
        MESSAGES,
        system_prompt="Consignes de test JSON",
        transport=httpx.MockTransport(handle_request),
    )

    assert result == '{"title": "Inscription"}'
    assert request_data["url"] == "https://llm.example/v1/chat/completions"
    assert request_data["authorization"] == "Bearer test-api-key"
    assert request_data["json"]["model"] == "test-model"
    assert request_data["json"]["response_format"] == {"type": "json_object"}
    # Les consignes passent en premier, suivies de toute la conversation.
    assert request_data["json"]["messages"] == [
        {"role": "system", "content": "Consignes de test JSON"},
        *MESSAGES,
    ]


def test_generate_completion_requires_configuration():
    # La configuration vide vient de conftest.py : aucun appel réseau possible.
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        LLM.generate_completion(MESSAGES, system_prompt="Consignes")


def test_generate_completion_rejects_an_empty_conversation():
    with pytest.raises(ValueError, match="ne peut pas être vide"):
        LLM.generate_completion([], system_prompt="Consignes")


# --- form_generator.py ---


def test_generate_form_parses_and_validates_the_llm_response(monkeypatch):
    monkeypatch.setattr(
        form_generator,
        "generate_completion",
        lambda messages, system_prompt: FORMULAIRE_JSON,
    )

    form = form_generator.generate_form(MESSAGES)

    assert form.title == "Inscription"
    assert form.questions[0].type == QuestionType.SHORT_TEXT


def test_generate_form_rejects_invalid_llm_output(monkeypatch):
    monkeypatch.setattr(
        form_generator,
        "generate_completion",
        lambda messages, system_prompt: '{"title": "Sans questions", "questions": []}',
    )

    with pytest.raises(ValidationError):
        form_generator.generate_form(MESSAGES)


def test_generate_form_sends_the_previous_error_to_the_llm(monkeypatch):
    envoyes = {}

    def faux_llm(messages, system_prompt):
        envoyes["messages"] = messages
        return FORMULAIRE_JSON

    monkeypatch.setattr(form_generator, "generate_completion", faux_llm)

    form_generator.generate_form(MESSAGES, previous_error="options manquantes")

    dernier = envoyes["messages"][-1]
    assert dernier["role"] == "user"
    assert "options manquantes" in dernier["content"]
    assert envoyes["messages"][:-1] == MESSAGES  # la conversation est intacte


def test_analyze_request_returns_the_questions(monkeypatch):
    monkeypatch.setattr(
        form_generator,
        "generate_completion",
        lambda messages, system_prompt: '{"questions": ["Quel public ?"]}',
    )

    analyse = form_generator.analyze_request(MESSAGES)

    assert analyse.questions == ["Quel public ?"]


def test_analyze_request_rejects_too_many_questions(monkeypatch):
    monkeypatch.setattr(
        form_generator,
        "generate_completion",
        lambda messages, system_prompt: '{"questions": ["a", "b", "c", "d"]}',
    )

    with pytest.raises(ValidationError):
        form_generator.analyze_request(MESSAGES)