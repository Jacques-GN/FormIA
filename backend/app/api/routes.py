"""Routes HTTP publiques du backend.

Parcours complet :
1. POST /forms/chat            -> l'agent répond ; un formulaire prêt arrive avec son empreinte.
2. GET  /auth/google/login     -> redirige l'utilisateur vers Google pour son accord.
3. GET  /auth/google/callback  -> Google revient ici ; on échange le code contre un jeton.
4. POST /forms/confirm         -> l'utilisateur confirme une version précise ; on crée le formulaire.

Liens : orchestrator.py (conversation), integrations/google_forms/ (oauth,
token_store, client), core/security.py (state OAuth), schemas/form.py (Form).
"""

import hashlib
import secrets
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, StringConstraints

from app.agents.orchestrator import lire_etat, traiter_message
from app.core.exceptions import (
    GoogleError,
    GoogleConnectionRequired,
    InvalidRequest,
    OperationPending,
    ResourceNotFound,
    VersionConflict,
)
from app.core.security import generate_oauth_state
from app.integrations.google_forms import client as google_client
from app.integrations.google_forms import creation_store, oauth, token_store
from app.schemas.form import Form
from app.services.proposal import render_clarification, render_proposal

router = APIRouter()

# Motif strict : l'identifiant de session ne peut contenir aucun caractère inattendu.
SESSION_ID_PATTERN = r"^[A-Za-z0-9-]{8,64}$"
SessionId = Annotated[str, StringConstraints(pattern=SESSION_ID_PATTERN)]
FormHash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


def empreinte_formulaire(form: Form) -> str:
    """Signature SHA-256 d'un formulaire : le moindre changement la modifie."""
    return hashlib.sha256(form.model_dump_json().encode("utf-8")).hexdigest()


class ChatRequest(BaseModel):
    """Ce que le client envoie à chaque message."""

    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
    ]
    session_id: SessionId | None = None  # absent au premier message


class ChatResponse(BaseModel):
    """Ce que le client reçoit : jamais l'état interne de l'agent."""

    session_id: str
    status: Literal["clarification", "form_ready", "failed", "info"]
    questions: list[str] = Field(default_factory=list)
    form: Form | None = None
    form_hash: str | None = None  # à renvoyer pour confirmer CETTE version
    # Texte déjà mis en forme par le serveur : le client l'affiche tel quel.
    # Il ne provient jamais d'une rédaction libre du LLM.
    message: str | None = None


class ConfirmRequest(BaseModel):
    """La confirmation porte sur une version précise (son empreinte)."""

    session_id: SessionId
    form_hash: FormHash


class ConfirmResponse(BaseModel):
    form_id: str
    responder_url: str  # lien à partager pour répondre au formulaire
    edit_url: str  # lien pour modifier le formulaire


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
            message=render_clarification(etat["questions"]),
        )

    if etat.get("formulaire"):
        form = Form.model_validate(etat["formulaire"])
        return ChatResponse(
            session_id=session_id,
            status="form_ready",
            form=form,
            form_hash=empreinte_formulaire(form),
            message=render_proposal(form),
        )

    if etat.get("message"):
        return ChatResponse(
            session_id=session_id,
            status="info",
            message=etat["message"],
        )

    # Message volontairement générique : le détail de l'erreur reste interne.
    return ChatResponse(
        session_id=session_id,
        status="failed",
        message="La génération du formulaire a échoué. Veuillez réessayer.",
    )


@router.get("/auth/google/login")
def google_login(
    session_id: Annotated[str, Query(pattern=SESSION_ID_PATTERN)],
) -> RedirectResponse:
    """Envoie le navigateur chez Google pour que l'utilisateur donne son accord."""
    state = generate_oauth_state()
    token_store.remember_state(state, session_id)  # pour retrouver la session au retour
    return RedirectResponse(oauth.build_authorization_url(state))


@router.get("/auth/google/callback")
def google_callback(
    code: Annotated[str | None, Query(max_length=2048)] = None,
    state: Annotated[str | None, Query(max_length=128)] = None,
    error: Annotated[str | None, Query(max_length=200)] = None,
) -> dict[str, str]:
    """Retour de Google : vérifie le « state », puis échange le code contre un jeton."""
    if error or not code or not state:
        raise InvalidRequest(
            "La connexion à Google a été refusée ou est incomplète."
        )

    session_id = token_store.consume_state(state)  # usage unique
    if session_id is None:
        raise InvalidRequest("Demande de connexion invalide ou expirée.")

    token = oauth.exchange_code_for_token(code)
    token_store.store_token(
        session_id, str(token["access_token"]), int(token["expires_in"])
    )
    return {
        "status": "connected",
        "message": "Connexion à Google réussie. Vous pouvez confirmer le formulaire.",
    }


@router.post("/forms/confirm")
def confirm(request: ConfirmRequest) -> ConfirmResponse:
    """Crée le formulaire dans Google, après confirmation de la version exacte.

    Idempotent : une seconde confirmation identique renvoie le résultat déjà
    obtenu sans rappeler Google. Si une création partielle a eu lieu, la
    confirmation reprend sur le même formulaire.
    """
    etat = lire_etat(request.session_id)
    if not etat.get("formulaire"):
        raise ResourceNotFound("Aucun formulaire prêt pour cette session.")

    # On utilise la copie du SERVEUR : le client ne dicte jamais ce qui est créé.
    form = Form.model_validate(etat["formulaire"])
    if not secrets.compare_digest(empreinte_formulaire(form), request.form_hash):
        raise VersionConflict(
            "Le formulaire a changé depuis l'aperçu. Relisez-le puis confirmez."
        )

    record, status = creation_store.try_begin(request.session_id, request.form_hash)
    if status == "completed":
        return ConfirmResponse(
            form_id=record.form_id or "",
            responder_url=record.responder_url or "",
            edit_url=record.edit_url or "",
        )
    if status == "pending":
        raise OperationPending()

    token = token_store.get_token(request.session_id)
    if token is None:
        creation_store.mark_failed(
            request.session_id, request.form_hash, "Connexion Google requise."
        )
        raise GoogleConnectionRequired()

    try:
        resultat = google_client.create_form(
            form,
            token,
            confirmed_form=form,
            existing_form_id=record.form_id,
            on_form_created=lambda form_id: creation_store.remember_form(
                request.session_id, request.form_hash, form_id
            ),
        )
    except google_client.PartialCreation as erreur:
        # Le formulaire existe : la prochaine confirmation reprendra dessus.
        creation_store.mark_retryable(
            request.session_id, request.form_hash, str(erreur)
        )
        raise GoogleError(str(erreur)) from erreur
    except Exception as erreur:
        creation_store.mark_failed(request.session_id, request.form_hash, str(erreur))
        raise

    creation_store.complete(
        request.session_id,
        request.form_hash,
        form_id=resultat["form_id"],
        responder_url=resultat["responder_url"],
        edit_url=resultat["edit_url"],
    )
    token_store.discard_token(request.session_id)  # moindre privilège
    return ConfirmResponse(**resultat)