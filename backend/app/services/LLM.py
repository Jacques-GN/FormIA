"""Adaptateur HTTP pour les fournisseurs compatibles avec l'API OpenAI."""

# Le nom de fichier conserve l'acronyme demandé par le projet.
# ruff: noqa: N999

import httpx

from app.core.config import settings

SYSTEM_PROMPT = """\
Tu conçois des formulaires. Réponds uniquement avec un objet JSON valide
conforme à ce format :
{
  "title": "Titre du formulaire",
  "description": "Description facultative",
  "questions": [
    {
      "title": "Intitulé de la question",
      "type": "short_text",
      "required": false,
      "options": []
    }
  ]
}
Les types autorisés sont : short_text, paragraph, multiple_choice,
checkboxes et dropdown. Les questions à choix doivent avoir au moins deux
options. Les questions de texte ne doivent pas avoir d'options.
"""

REQUEST_TIMEOUT_SECONDS = 30.0


def generate_completion(
    prompt: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Envoie une demande au fournisseur configuré et retourne le contenu JSON."""
    if not settings.llm_api_key:
        raise RuntimeError("La variable LLM_API_KEY n'est pas configurée.")
    if not settings.llm_model:
        raise RuntimeError("La variable LLM_MODEL n'est pas configurée.")
    if not settings.llm_base_url:
        raise RuntimeError("La variable LLM_BASE_URL n'est pas configurée.")

    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
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
