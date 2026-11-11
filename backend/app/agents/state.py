"""État partagé entre les étapes du graphe de génération."""

from dataclasses import dataclass

from app.schemas.form import Form


@dataclass
class FormRequestState:
    prompt: str
    form: Form | None = None
