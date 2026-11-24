"""Application FastAPI : assemblage des routes et conversion des erreurs.

Un seul endroit traduit les exceptions en réponses HTTP au format uniforme
`{code, message}`. Aucun détail interne (trace, réponse d'un fournisseur,
contenu d'un document) n'est renvoyé au client.
"""

import logging
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.exceptions import FormIAError

logger = logging.getLogger("formia")

app = FastAPI(
    title="FormIA",
    description="L'intelligence africaine, au service de vos idées.",
    version="0.1.0",
)
app.include_router(router)

# Code métier associé aux erreurs HTTP levées par FastAPI lui-même.
_CODE_BY_STATUS = {
    400: "invalid_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "version_conflict",
    422: "validation_error",
    429: "quota_exceeded",
    502: "upstream_error",
    503: "service_unavailable",
}


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Ajoute un identifiant de requête, utile pour corréler les journaux."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


@app.exception_handler(FormIAError)
async def formia_error_handler(request: Request, exc: FormIAError) -> JSONResponse:
    """Convertit une erreur métier en réponse stable et sans détail interne."""
    if exc.http_status >= 500:
        logger.error(
            "erreur_metier",
            extra={"request_id": _request_id(request), "code": exc.code},
            exc_info=exc,
        )
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message},
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Uniformise les erreurs HTTP levées par FastAPI ou une dépendance."""
    message = exc.detail if isinstance(exc.detail, str) else "La demande a échoué."
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": _CODE_BY_STATUS.get(exc.status_code, "http_error"),
            "message": message,
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Ne renvoie pas le détail des champs : seulement un message générique."""
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": "La demande est invalide.",
        },
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Erreur inattendue : journalisée côté serveur, message générique au client."""
    request_id = _request_id(request)
    logger.exception("erreur_inattendue", extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content={
            "code": "internal_error",
            "message": "Une erreur interne est survenue.",
        },
        headers={"X-Request-ID": request_id},
    )
