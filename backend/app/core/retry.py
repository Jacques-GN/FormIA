"""Relances contrôlées pour les pannes passagères (429 et 5xx).

Utilisé uniquement pour les appels idempotents : une complétion LLM peut être
renvoyée sans effet de bord externe. Les créations Google (non idempotentes)
ne passent jamais par ce module.
"""

import random
import time
from collections.abc import Callable

import httpx

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def post_with_retries(
    client: httpx.Client,
    url: str,
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 4.0,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs,
) -> httpx.Response:
    """Envoie une requête POST et relance sur 429/5xx avec attente croissante.

    `Retry-After` est respecté lorsqu'il contient un nombre de secondes.
    La dernière réponse est retournée sans lever d'exception : l'appelant
    décide du message métier. `sleep` est injectable pour les tests.
    """
    if attempts < 1:
        raise ValueError("attempts doit valoir au moins 1.")

    response: httpx.Response | None = None
    for attempt in range(attempts):
        response = client.post(url, **kwargs)
        if response.status_code not in RETRYABLE_STATUS_CODES:
            return response
        if attempt == attempts - 1:
            break

        delay = min(max_delay, base_delay * (2**attempt))
        delay *= 0.5 + random.random()  # jitter : évite les relances synchronisées
        retry_after = response.headers.get("Retry-After", "")
        if retry_after.isdigit():
            delay = max(delay, min(float(retry_after), max_delay))
        sleep(delay)

    # `response` ne peut pas être None : attempts >= 1.
    return response
