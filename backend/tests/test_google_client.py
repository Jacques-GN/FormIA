"""Tests du client Google Forms, avec un réseau simulé (httpx.MockTransport)."""

import json

import httpx
import pytest

from app.integrations.google_forms import client
from app.schemas.form import Form, Question, QuestionType

FORM = Form(
    title="Inscription",
    description="Merci de répondre.",
    questions=[
        Question(title="Nom", type=QuestionType.SHORT_TEXT, required=True),
        Question(title="Présentation", type=QuestionType.PARAGRAPH),
    ],
)


def test_text_questions_are_translated():
    court = client.question_to_item(
        Question(title="Nom", type=QuestionType.SHORT_TEXT)
    )
    long = client.question_to_item(
        Question(title="Détails", type=QuestionType.PARAGRAPH)
    )

    assert court["questionItem"]["question"]["textQuestion"] == {"paragraph": False}
    assert long["questionItem"]["question"]["textQuestion"] == {"paragraph": True}


def test_choice_questions_are_translated():
    attendu = {
        QuestionType.MULTIPLE_CHOICE: "RADIO",
        QuestionType.CHECKBOXES: "CHECKBOX",
        QuestionType.DROPDOWN: "DROP_DOWN",
    }

    for type_formia, type_google in attendu.items():
        item = client.question_to_item(
            Question(title="Choix", type=type_formia, options=["A", "B"])
        )
        choix = item["questionItem"]["question"]["choiceQuestion"]
        assert choix["type"] == type_google
        assert choix["options"] == [{"value": "A"}, {"value": "B"}]


def test_form_to_requests_keeps_indexes_in_order():
    requests = client.form_to_requests(FORM)

    assert requests[0]["updateFormInfo"]["info"]["description"] == "Merci de répondre."
    indexes = [r["createItem"]["location"]["index"] for r in requests[1:]]
    assert indexes == [0, 1]


def test_form_to_requests_can_resume_after_existing_items():
    requests = client.form_to_requests(FORM, first_question_index=1)

    # La description est idempotente, seule la question absente est recréée.
    creates = [r for r in requests if "createItem" in r]
    assert len(creates) == 1
    assert creates[0]["createItem"]["location"]["index"] == 1
    assert creates[0]["createItem"]["item"]["title"] == "Présentation"


def test_create_form_creates_then_updates():
    appels = []

    def handle(request: httpx.Request) -> httpx.Response:
        appels.append((request.method, str(request.url), json.loads(request.content)))
        if request.url.path.endswith(":batchUpdate"):
            return httpx.Response(200, json={"replies": []})
        return httpx.Response(
            200,
            json={
                "formId": "form-123",
                "responderUri": "https://forms.gle/abc",
            },
        )

    resultat = client.create_form(
        FORM,
        "jeton-secret",
        confirmed_form=FORM,
        transport=httpx.MockTransport(handle),
    )

    assert resultat == {
        "form_id": "form-123",
        "responder_url": "https://forms.gle/abc",
        "edit_url": "https://docs.google.com/forms/d/form-123/edit",
    }
    assert appels[0][0] == "POST"
    assert appels[0][2]["info"]["title"] == "Inscription"
    assert appels[1][1].endswith("/form-123:batchUpdate")
    # Le jeton ne doit jamais figurer dans le corps envoyé.
    assert "jeton-secret" not in json.dumps(appels)


def test_create_form_resumes_on_the_same_form():
    appels = []

    def handle(request: httpx.Request) -> httpx.Response:
        appels.append((request.method, str(request.url)))
        if request.method == "GET":
            return httpx.Response(200, json={"formId": "form-123", "items": []})
        return httpx.Response(200, json={"replies": []})

    resultat = client.create_form(
        FORM,
        "jeton",
        confirmed_form=FORM,
        existing_form_id="form-123",
        transport=httpx.MockTransport(handle),
    )

    assert resultat["form_id"] == "form-123"
    assert [appel[0] for appel in appels] == ["GET", "POST"]
    assert ":batchUpdate" in appels[1][1]


def test_create_form_does_not_duplicate_existing_questions():
    envoye = {}

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "formId": "form-123",
                    "items": [{"title": "Nom", "questionItem": {}}],
                },
            )
        envoye.update(json.loads(request.content))
        return httpx.Response(200, json={"replies": []})

    client.create_form(
        FORM,
        "jeton",
        confirmed_form=FORM,
        existing_form_id="form-123",
        transport=httpx.MockTransport(handle),
    )

    creates = [r for r in envoye["requests"] if "createItem" in r]
    assert len(creates) == 1
    assert creates[0]["createItem"]["location"]["index"] == 1


def test_create_form_signals_a_partial_creation():
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(":batchUpdate"):
            return httpx.Response(500, json={"error": "interne"})
        return httpx.Response(200, json={"formId": "form-123"})

    with pytest.raises(client.PartialCreation) as erreur:
        client.create_form(
            FORM,
            "jeton",
            confirmed_form=FORM,
            transport=httpx.MockTransport(handle),
        )

    assert erreur.value.form_id == "form-123"
    assert "form-123/edit" in erreur.value.message
    assert "interne" not in erreur.value.message  # aucun détail Google recopié


def test_create_form_refuses_an_unconfirmed_version():
    with pytest.raises(PermissionError):
        client.create_form(
            FORM,
            "jeton",
            confirmed_form=FORM.model_copy(update={"title": "Autre titre"}),
        )
