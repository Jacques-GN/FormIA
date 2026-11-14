"""Adaptateur HTTP pour les fournisseurs compatibles avec l'API OpenAI.

Seul fichier qui parle au fournisseur de modèle : il envoie une conversation
et retourne le texte JSON reçu. Il ne connaît ni les formulaires ni les
consignes métier (elles sont dans services/form_generator.py).
"""

# Le nom de fichier conserve l'acronyme demandé par le projet.
# ruff: noqa: N999

import httpx

from app.core.config import settings

REQUEST_TIMEOUT_SECONDS = 30.0


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
        raise RuntimeError("La variable LLM_API_KEY n'est pas configurée.")
    if not settings.llm_model:
        raise RuntimeError("La variable LLM_MODEL n'est pas configurée.")
    if not settings.llm_base_url:
        raise RuntimeError("La variable LLM_BASE_URL n'est pas configurée.")

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

    with httpx.Client(
        timeout=REQUEST_TIMEOUT_SECONDS,
        transport=transport,
    ) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()

    response_data = response.json()
    if not isinstance(response_data, dict):
        raise TypeError("La réponse du fournisseur LLM doit être un objet JSON.")

    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("La réponse du fournisseur LLM ne contient aucun choix.")

    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise TypeError("La réponse du fournisseur LLM ne contient pas de texte.")

    content = message["content"].strip()
    if not content:
        raise ValueError("Le fournisseur LLM a retourné une réponse vide.")

    return content