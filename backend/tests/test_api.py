"""Tests de l'API Formia."""

from fastapi.testclient import TestClient
from app.api import routes
from app.schemas.form import Form, Question, QuestionType
from app.main import app

# Le client de test simule un navigateur : il appelle l'API sans lancer le serveur.
client = TestClient(app)


def test_home_returns_welcome_message():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"Message": "Bienvenue sur FormIA", "status": "online"}


def test_health_endpoint_returns_healthy():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_chat_returns_clarification_questions(monkeypatch):
    monkeypatch.setattr(
        routes,
        "traiter_message",
        lambda message, session_id: {"questions": ["Quel public ?"]},
    )

    response = client.post("/forms/chat", json={"message": "Un formulaire"})

    assert response.status_code == 200
    corps = response.json()
    assert corps["status"] == "clarification"
    assert corps["questions"] == ["Quel public ?"]
    assert "Quel public ?" in corps["message"]
    assert corps["session_id"]  # créé par le serveur au premier message


def test_chat_returns_the_generated_form(monkeypatch):
    formulaire = Form(
        title="Tournoi",
        questions=[Question(title="Nom", type=QuestionType.SHORT_TEXT)],
    ).model_dump(mode="json")
    monkeypatch.setattr(
        routes,
        "traiter_message",
        lambda message, session_id: {"formulaire": formulaire},
    )

    response = client.post("/forms/chat", json={"message": "Un formulaire"})

    corps = response.json()
    assert corps["status"] == "form_ready"
    assert corps["form"]["title"] == "Tournoi"
    # Le texte affiché est rendu par le serveur, pas rédigé par le LLM.
    assert "1. Nom (réponse courte)" in corps["message"]
    assert "Aucun formulaire n'a encore été créé" in corps["message"]


def test_chat_hides_internal_errors_when_generation_fails(monkeypatch):
    monkeypatch.setattr(
        routes,
        "traiter_message",
        lambda message, session_id: {"erreur": "détail interne confidentiel"},
    )

    response = client.post("/forms/chat", json={"message": "Un formulaire"})

    assert response.json()["status"] == "failed"
    assert "confidentiel" not in response.text


def test_chat_keeps_the_given_session_id(monkeypatch):
    recus = {}

    def faux_agent(message, session_id):
        recus["session_id"] = session_id
        return {"questions": ["Quel public ?"]}

    monkeypatch.setattr(routes, "traiter_message", faux_agent)

    response = client.post(
        "/forms/chat",
        json={"message": "Un formulaire", "session_id": "abcdefgh-1234"},
    )

    assert recus["session_id"] == "abcdefgh-1234"
    assert response.json()["session_id"] == "abcdefgh-1234"


def test_chat_rejects_an_empty_message():
    response = client.post("/forms/chat", json={"message": "   "})

    assert response.status_code == 422


def test_chat_rejects_an_invalid_session_id():
    response = client.post(
        "/forms/chat",
        json={"message": "Un formulaire", "session_id": "id invalide !"},
    )

    assert response.status_code == 422


def test_chat_never_creates_a_google_form(monkeypatch):
    from app.integrations.google_forms import client as google_client

    def interdit(*args, **kwargs):
        raise AssertionError("La conversation ne doit jamais créer de formulaire.")

    monkeypatch.setattr(google_client, "create_form", interdit)
    formulaire = Form(
        title="Tournoi",
        questions=[Question(title="Nom", type=QuestionType.SHORT_TEXT)],
    ).model_dump(mode="json")
    monkeypatch.setattr(
        routes, "traiter_message", lambda message, session_id: {"formulaire": formulaire}
    )

    response = client.post("/forms/chat", json={"message": "Un formulaire"})

    assert response.status_code == 200
    assert response.json()["status"] == "form_ready"