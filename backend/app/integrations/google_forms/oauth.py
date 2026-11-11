"""Préparation de l'URL OAuth Google ; les routes de connexion restent à créer."""

from urllib.parse import urlencode

from app.core.config import settings

AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
FORMS_SCOPE = "https://www.googleapis.com/auth/forms.body"


def build_authorization_url(state: str) -> str:
    if not state:
        raise ValueError("Le paramètre OAuth state est obligatoire.")
    if not settings.google_client_id or not settings.google_redirect_uri:
        raise RuntimeError("La configuration OAuth Google est incomplète.")

    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": FORMS_SCOPE,
            "state": state,
            "access_type": "offline",
        }
    )
    return f"{AUTHORIZATION_URL}?{query}"
