"""Routes HTTP publiques du backend.

Liens : orchestrator.py (traiter_message fait avancer la conversation),
schemas/form.py (le modèle Form renvoyé au client). main.py branche ce routeur
sur l'application.
"""

from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field, StringConstraints

from app.agents.orchestrator import traiter_message
from app.schemas.form import Form

router = APIRouter()


class ChatRequest(BaseModel):
    """Ce que le client envoie à chaque message."""

    # Espaces retirés, vide refusé, taille bornée : on ne fait pas confiance à l'entrée.
    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
    ]
    # Absent au premier message. Le motif interdit tout caractère inattendu.
    session_id: (
        Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{8,64}$")] | None
    ) = None


class ChatResponse(BaseModel):
    """Ce que le client reçoit : jamais l'état interne de l'agent."""

    session_id: str  # à renvoyer pour continuer la conversation
    status: Literal["clarification", "form_ready", "failed"]
    questions: list[str] = Field(default_factory=list)
    form: Form | None = None
    message: str | None = None


@router.get("/")
def accueil() -> dict[str, str]:
    return {"Message": "Bienvenue sur FormIA", "status": "online"}


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@router.post("/forms/chat")
def chat(request: ChatRequest) -> ChatResponse:
    """Fait avancer la conversation. Ne crée rien dans Google Forms."""
    session_id = request.session_id or str(uuid4())
    etat = traiter_message(request.message, session_id)

    if etat.get("questions"):
        return ChatResponse(
            session_id=session_id,
            status="clarification",
            questions=etat["questions"],
        )

    if etat.get("formulaire"):
        return ChatResponse(
            session_id=session_id,
            status="form_ready",
            # Revalidé avec le schéma Form avant de sortir de l'API.
            form=Form.model_validate(etat["formulaire"]),
        )

    # Message volontairement générique : le détail de l'erreur reste interne.
    return ChatResponse(
        session_id=session_id,
        status="failed",
        message="La génération du formulaire a échoué. Veuillez réessayer.",
    )