"""Tests de l'API Formia."""

from fastapi.testclient import TestClient

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