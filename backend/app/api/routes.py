"""Routes HTTP publiques du backend."""

from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StringConstraints

from app.agents.orchestrator import orchestrate_form_request
from app.schemas.form import Form

router = APIRouter()


class GenerateFormRequest(BaseModel):
    """Corps de la requête : la demande de l'utilisateur."""

    # Pydantic retire les espaces autour, refuse le vide et limite la taille
    # (règle 6.4 : valider et borner les données reçues par l'API).
    prompt: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
    ]


@router.get("/")
def accueil() -> dict[str, str]:
    return {"Message": "Bienvenue sur FormIA", "status": "online"}


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


# Fonction "def" (pas "async def") : le graphe et httpx sont synchrones,
# FastAPI l'exécute alors dans un thread sans bloquer le serveur.
@router.post("/forms/generate")
def generate_form(request: GenerateFormRequest) -> Form:
    """Génère la structure d'un formulaire. Ne crée rien dans Google."""
    try:
        return orchestrate_form_request(request.prompt)
    except (httpx.HTTPError, ValueError, TypeError) as error:
        # Message volontairement générique : pas de détails internes au client.
        raise HTTPException(
            status_code=502,
            detail="La génération du formulaire a échoué. Veuillez réessayer.",
        ) from error