"""Tests des relances contrôlées sur les pannes passagères."""

import httpx

from app.core.retry import post_with_retries


def test_retries_on_429_and_honours_retry_after():
    reponses = [
        httpx.Response(429, headers={"Retry-After": "2"}),
        httpx.Response(200, json={"ok": True}),
    ]
    appels = []
    attentes = []

    def handle(request: httpx.Request) -> httpx.Response:
        appels.append(request)
        return reponses.pop(0)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        response = post_with_retries(
            client, "https://exemple.test", sleep=attentes.append
        )

    assert response.status_code == 200
    assert len(appels) == 2
    assert attentes[0] >= 2.0  # Retry-After respecté


def test_does_not_retry_a_client_error():
    appels = []

    def handle(request: httpx.Request) -> httpx.Response:
        appels.append(request)
        return httpx.Response(400, json={"erreur": "demande invalide"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        response = post_with_retries(client, "https://exemple.test", sleep=lambda _: None)

    assert response.status_code == 400
    assert len(appels) == 1


def test_stops_after_the_maximum_number_of_attempts():
    appels = []

    def handle(request: httpx.Request) -> httpx.Response:
        appels.append(request)
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        response = post_with_retries(
            client, "https://exemple.test", attempts=3, sleep=lambda _: None
        )

    assert response.status_code == 503
    assert len(appels) == 3
