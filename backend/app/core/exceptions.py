"""Exceptions métier de FormIA.

Un seul point de conversion en réponse HTTP : les gestionnaires enregistrés
dans `app/main.py`. Les autres modules lèvent ces exceptions ; ils ne
construisent jamais de réponse HTTP et n'exposent jamais de détail interne.

Chaque exception porte un `code` stable pour le client et un `http_status`.
Le message affiché reste volontairement court et sans information sensible.
"""


class FormIAError(Exception):
    """Base de toutes les erreurs métier de FormIA."""

    code = "internal_error"
    http_status = 500
    default_message = "Une erreur interne est survenue."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class InvalidRequest(FormIAError):
    """La demande du client est incomplète ou mal formée."""

    code = "invalid_request"
    http_status = 400
    default_message = "La demande est invalide."


class MissingConfiguration(FormIAError):
    """Une variable d'environnement obligatoire manque."""

    code = "configuration_missing"
    http_status = 500
    default_message = "La configuration du service est incomplète."


class LLMUnavailable(FormIAError):
    """Le fournisseur de modèle est indisponible ou a dépassé ses quotas."""

    code = "llm_unavailable"
    http_status = 503
    default_message = (
        "Le service de génération est momentanément indisponible. "
        "Votre conversation est conservée : réessayez dans un instant."
    )


class InvalidLLMOutput(FormIAError):
    """Le fournisseur a répondu, mais pas sous une forme exploitable."""

    code = "llm_invalid_output"
    http_status = 502
    default_message = "La réponse du service de génération n'est pas exploitable."


class GoogleConnectionRequired(FormIAError):
    """Aucun jeton Google valide pour cette session."""

    code = "google_connection_required"
    http_status = 401
    default_message = "Connexion à Google requise : ouvrez /auth/google/login."


class GoogleError(FormIAError):
    """Google Forms a refusé ou n'a pas pu traiter la demande."""

    code = "google_error"
    http_status = 502
    default_message = "Google Forms n'a pas pu traiter la demande."


class ResourceNotFound(FormIAError):
    """La ressource demandée n'existe pas, ou pas pour cet appelant."""

    code = "not_found"
    http_status = 404
    default_message = "La ressource demandée est introuvable."


class VersionConflict(FormIAError):
    """La version confirmée n'est plus la version courante."""

    code = "version_conflict"
    http_status = 409
    default_message = "La ressource a changé. Relisez-la puis confirmez."


class QuotaExceeded(FormIAError):
    """Trop de demandes pour la fenêtre courante."""

    code = "quota_exceeded"
    http_status = 429
    default_message = "Trop de demandes. Réessayez dans un instant."


class OperationPending(FormIAError):
    """Une opération identique est déjà en cours."""

    code = "operation_pending"
    http_status = 409
    default_message = "Une opération est déjà en cours pour cette demande."
