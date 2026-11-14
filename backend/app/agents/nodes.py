"""Étapes exécutées par le graphe de génération de formulaire."""

from app.agents.state import FormRequestState
from app.services.form_generator import generate_form as generate_form_from_prompt


def validate_request(state: FormRequestState) -> dict:
    """Nettoie la demande et refuse une demande vide."""
    prompt = state.prompt.strip()
    if not prompt:
        raise ValueError("La demande de formulaire ne peut pas être vide.")
    return {"prompt": prompt}  # champ à mettre à jour dans l'état


def generate_form(state: FormRequestState) -> dict:
    """Appelle le service de génération (le LLM) et stocke le formulaire."""
    return {"form": generate_form_from_prompt(state.prompt)}