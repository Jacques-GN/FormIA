"""Tests de l'adaptateur LLM et de la validation des réponses générées."""

import json

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.form import QuestionType
from app.services import LLM, form_generator


def configured_settings() -> Settings:
    return Settings(
        llm_api_key="test-api-key",
        llm_model="test-model",
        llm_base_url="https://llm.example/v1",
    )


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
        "Créer un formulaire d'inscription",
        transport=httpx.MockTransport(handle_request),
    )

    assert result == '{"title": "Inscription"}'
    assert request_data["url"] == "https://llm.example/v1/chat/completions"
    assert request_data["authorization"] == "Bearer test-api-key"
    assert request_data["json"]["model"] == "test-model"
    assert request_data["json"]["response_format"] == {"type": "json_object"}


def test_generate_completion_requires_configuration(monkeypatch):
    monkeypatch.setattr(LLM, "settings", Settings())

    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        LLM.generate_completion("Créer un formulaire")


def test_generate_form_parses_and_validates_the_llm_response(monkeypatch):
    response = json.dumps(
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
    monkeypatch.setattr(form_generator, "generate_completion", lambda prompt: response)

    form = form_generator.generate_form(" Créer un formulaire ")

    assert form.title == "Inscription"
    assert form.questions[0].type == QuestionType.SHORT_TEXT


def test_generate_form_rejects_invalid_llm_output(monkeypatch):
    monkeypatch.setattr(
        form_generator,
        "generate_completion",
        lambda prompt: '{"title": "Formulaire sans questions", "questions": []}',
    )

    with pytest.raises(ValidationError):
        form_generator.generate_form("Créer un formulaire")


def test_generate_form_rejects_an_empty_prompt():
    with pytest.raises(ValueError, match="ne peut pas être vide"):
        form_generator.generate_form("   ")
