"""Adaptateur HTTP pour les fournisseurs compatibles avec l'API OpenAI.

Seul fichier qui parle au fournisseur de modèle : il envoie une conversation
et retourne le texte JSON reçu. Il ne connaît ni les formulaires ni les
consignes métier (elles sont dans services/form_generator.py).

Fiabilité : relance sur 429/5xx (voir core/retry.py), erreurs traduites en
exceptions métier. Mesure : durée, modèle, statut et nombre de tokens sont
journalisés, jamais le contenu des messages.
"""

# Le nom de fichier conserve l'acronyme demandé par le projet.
# ruff: noqa: N999

import logging
import time

import httpx

from app.core.config import settings
from app.core.exceptions import InvalidLLMOutput, LLMUnavailable, MissingConfiguration
from app.core.retry import post_with_retries

REQUEST_TIMEOUT_SECONDS = 30.0

logger = logging.getLogger("formia.llm")


def generate_completion(
    messages: list[dict[str, str]],
    *,
    system_prompt: str,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Envoie la conversation au fournisseur configuré et retourne le JSON reçu.

    messages : l'historique, au format {"role": "user" | "assistant", "content": "..."}.
    system_prompt : les consignes données au modèle pour cet appel.
    transport : sert uniquement aux tests, pour simuler le réseau.
    """
    if not messages:
        raise ValueError("La conversation envoyée au LLM ne peut pas être vide.")
    if not settings.llm_api_key:
        raise MissingConfiguration("La variable LLM_API_KEY n'est pas configurée.")
    if not settings.llm_model:
        raise MissingConfiguration("La variable LLM_MODEL n'est pas configurée.")
    if not settings.llm_base_url:
        raise MissingConfiguration("La variable LLM_BASE_URL n'est pas configurée.")

    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.llm_model,
        # Le LLM n'a pas de mémoire : on lui renvoie les consignes (system)
        # suivies de toute la conversation à chaque appel.
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        # Garantit un JSON syntaxiquement valide, pas conforme à notre schéma :
        # la validation Pydantic reste nécessaire.
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}

    started_at = time.perf_counter()
    status_code: int | None = None
    usage: dict = {}
    try:
        with httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            transport=transport,
        ) as client:
            response = post_with_retries(client, url, headers=headers, json=payload)
        status_code = response.status_code

        if status_code >= 400:
            raise LLMUnavailable()

        try:
            response_data = response.json()
        except ValueError as error:
            raise InvalidLLMOutput() from error
        if not isinstance(response_data, dict):
            raise InvalidLLMOutput()

        choices = response_data.get("choices")
        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(choices[0], dict)
        ):
            raise InvalidLLMOutput("La réponse du fournisseur ne contient aucun choix.")

        message = choices[0].get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise InvalidLLMOutput(
                "La réponse du fournisseur ne contient pas de texte."
            )

        content = message["content"].strip()
        if not content:
            raise InvalidLLMOutput("Le fournisseur a retourné une réponse vide.")

        if isinstance(response_data.get("usage"), dict):
            usage = response_data["usage"]
        return content

    except httpx.HTTPError as error:
        raise LLMUnavailable() from error
    finally:
        # Journal sans contenu : uniquement des mesures d'exploitation.
        logger.info(
            "llm_call",
            extra={
                "llm_model": settings.llm_model,
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        )
