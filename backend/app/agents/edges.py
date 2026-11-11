"""Décisions de transition entre les étapes du graphe."""

from app.agents.state import FormRequestState


def next_step(current_step: str, state: FormRequestState) -> str | None:
    if current_step == "validate_request":
        return "generate_form"
    if current_step == "generate_form":
        return None if state.form is not None else "generate_form"

    raise ValueError(f"Étape inconnue dans le graphe : {current_step}")
