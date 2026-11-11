"""Génération de formulaires ; aucun fournisseur LLM n'est configuré pour l'instant."""

from app.schemas.form import Form


def generate_form(prompt: str) -> Form:
    raise NotImplementedError(
        "La génération nécessite de choisir et configurer un fournisseur LLM."
    )
