"""Connexion OAuth 2.0 à Google : URL de consentement et échange du code.

Liens avec les autres fichiers
------------------------------
- core/config.py     : fournit l'ID client, le secret et l'URI de redirection.
- core/security.py   : génère et vérifie le paramètre « state ».
- routes.py          : appellera ces fonctions (routes de connexion, fichier suivant).
- client.py          : utilisera le jeton d'accès obtenu ici.

Ce fichier ne stocke rien : il construit l'URL et échange le code.
Sécurité : le secret client et les jetons ne sont jamais affichés ni enregistrés.
"""

from urllib.parse import urlencode

import httpx

from app.core.config import settings

AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
FORMS_SCOPE = "https://www.googleapis.com/auth/forms.body"
REQUEST_TIMEOUT_SECONDS = 30.0


def build_authorization_url(state: str) -> str:
    """Construit l'URL de Google où l'utilisateur donne son accord.

    state : valeur aléatoire gardée côté serveur, comparée au retour de Google.
    Pas de access_type=offline : on ne demande pas de refresh token, dont
    on n'a pas besoin (le jeton sert juste après la confirmation).
    """
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
        }
    )
    return f"{AUTHORIZATION_URL}?{query}"


def exchange_code_for_token(
    code: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, object]:
    """Échange le code d'autorisation (à usage unique) contre un jeton d'accès.

    Côté serveur uniquement : l'échange utilise le secret client.
    Retourne {"access_token": str, "expires_in": int}.
    transport : sert uniquement aux tests, pour simuler le réseau.
    """
    if not code:
        raise ValueError("Le code d'autorisation est obligatoire.")
    if not (
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_redirect_uri
    ):
        raise RuntimeError("La configuration OAuth Google est incomplète.")

    with httpx.Client(
        timeout=REQUEST_TIMEOUT_SECONDS,
        transport=transport,
    ) as client:
        response = client.post(
            TOKEN_URL,
            # data= : Google attend un formulaire encodé, pas du JSON.
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()

    data = response.json()
    access_token = data.get("access_token") if isinstance(data, dict) else None
    if not isinstance(access_token, str) or not access_token:
        raise ValueError("La réponse de Google ne contient pas de jeton d'accès.")

    expires_in = data.get("expires_in")
    return {
        "access_token": access_token,
        # 3600 s par défaut si Google n'indique pas la durée.
        "expires_in": expires_in if isinstance(expires_in, int) else 3600,
    }