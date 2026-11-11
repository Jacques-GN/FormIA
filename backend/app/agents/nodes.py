"""Étapes exécutées par le graphe de génération de formulaire."""

from app.agents.state import FormRequestState
from app.services.form_generator import generate_form as generate_form_from_prompt


def validate_request(state: FormRequestState) -> None:
    state.prompt = state.prompt.strip()
    if not state.prompt:
        raise ValueError("La demande de formulaire ne peut pas être vide.")


def generate_form(state: FormRequestState) -> None:
    state.form = generate_form_from_prompt(state.prompt)
