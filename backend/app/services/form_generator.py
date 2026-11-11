"""Génération et validation des formulaires proposés par le LLM."""

from app.schemas.form import Form
from app.services.LLM import generate_completion


def generate_form(prompt: str) -> Form:
    if not prompt.strip():
        raise ValueError("La demande de formulaire ne peut pas être vide.")

    response = generate_completion(prompt.strip())
    return Form.model_validate_json(response)
