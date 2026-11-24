"""Tests de la route de confirmation : refus, succès et idempotence."""

from fastapi.testclient import TestClient

from app.api import routes
from app.integrations.google_forms import client as google_client
from app.integrations.google_forms import creation_store, token_store
from app.main import app
from app.schemas.form import Form, Question, QuestionType

client = TestClient(app)

SESSION = "abcdefgh-1234"
FORM = Form(
    title="Inscription",
    questions=[Question(title="Nom", type=QuestionType.SHORT_TEXT)],
)
FORM_HASH = routes.empreinte_formulaire(FORM)


def prepare(monkeypatch, *, with_token: bool = True):
    monkeypatch.setattr(
        routes,
        "lire_etat",
        lambda session_id: {"formulaire": FORM.model_dump(mode="json")},
    )
    if with_token:
        token_store.store_token(SESSION, "jeton-google", 3600)


def confirmer():
    return client.post(
        "/forms/confirm",
        json={"session_id": SESSION, "form_hash": FORM_HASH},
    )


def test_confirm_returns_404_without_a_ready_form(monkeypatch):
    monkeypatch.setattr(routes, "lire_etat", lambda session_id: {})

    response = confirmer()

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_confirm_refuses_a_stale_hash(monkeypatch):
    prepare(monkeypatch)
    autre = Form(
        title="Autre",
        questions=[Question(title="Nom", type=QuestionType.SHORT_TEXT)],
    )

    response = client.post(
        "/forms/confirm",
        json={"session_id": SESSION, "form_hash": routes.empreinte_formulaire(autre)},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "version_conflict"


def test_confirm_requires_a_google_connection(monkeypatch):
    prepare(monkeypatch, with_token=False)

    response = confirmer()

    assert response.status_code == 401
    assert response.json()["code"] == "google_connection_required"


def test_confirm_creates_the_form_once(monkeypatch):
    prepare(monkeypatch)
    appels = []

    def faux_create(form, token, *, confirmed_form, existing_form_id, on_form_created):
        appels.append(existing_form_id)
        on_form_created("form-1")
        return {
            "form_id": "form-1",
            "responder_url": "https://forms.gle/abc",
            "edit_url": "https://docs.google.com/forms/d/form-1/edit",
        }

    monkeypatch.setattr(google_client, "create_form", faux_create)

    premiere = confirmer()
    seconde = confirmer()

    assert premiere.status_code == 200
    assert premiere.json()["form_id"] == "form-1"
    assert "jeton-google" not in premiere.text  # aucun jeton dans la réponse
    assert seconde.status_code == 200
    assert seconde.json() == premiere.json()
    # Le second appel ne doit pas rappeler Google.
    assert appels == [None]
    # Le jeton est oublié après succès (moindre privilège).
    assert token_store.get_token(SESSION) is None


def test_confirm_resumes_after_a_partial_creation(monkeypatch):
    prepare(monkeypatch)
    edit_url = "https://docs.google.com/forms/d/form-1/edit"
    appels = []

    def faux_create(form, token, *, confirmed_form, existing_form_id, on_form_created):
        appels.append(existing_form_id)
        if existing_form_id is None:
            on_form_created("form-1")
            raise google_client.PartialCreation("form-1", edit_url)
        return {
            "form_id": "form-1",
            "responder_url": "https://forms.gle/abc",
            "edit_url": edit_url,
        }

    monkeypatch.setattr(google_client, "create_form", faux_create)

    premiere = confirmer()
    assert premiere.status_code == 502
    assert premiere.json()["code"] == "google_error"
    assert edit_url in premiere.json()["message"]

    record = creation_store.get(SESSION, FORM_HASH)
    assert record.form_id == "form-1"
    # L'échec est récupérable : le jeton reste disponible pour la reprise.
    assert token_store.get_token(SESSION) is not None

    seconde = confirmer()
    assert seconde.status_code == 200
    assert appels == [None, "form-1"]
    # Une fois la création terminée, le jeton est oublié.
    assert token_store.get_token(SESSION) is None


def test_confirm_rejects_a_malformed_hash(monkeypatch):
    prepare(monkeypatch)

    response = client.post(
        "/forms/confirm",
        json={"session_id": SESSION, "form_hash": "pas-un-hash"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
