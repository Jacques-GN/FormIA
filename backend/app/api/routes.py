"""Routes HTTP publiques du backend."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def accueil() -> dict[str, str]:
    return {"Message": "Bienvenue sur FormIA", "status": "online"}


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
