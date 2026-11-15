"""Registre en mémoire des « state » OAuth et des jetons d'accès Google.

Liens avec les autres fichiers
------------------------------
- routes.py : remember_state() avant la redirection vers Google ; consume_state()
              et store_token() au retour ; get_token() et discard_token() à la
              création du formulaire.
- oauth.py  : fournit le jeton qu'on range ici.

Limites : tout est en RAM (perdu au redémarrage, non partagé entre processus).
Sécurité : un jeton ne doit jamais être affiché, ni écrit dans un log ou une réponse.
"""

import threading
import time

STATE_LIFETIME_SECONDS = 600  # un « state » ne vaut que 10 minutes
TOKEN_SAFETY_MARGIN_SECONDS = 60  # on oublie le jeton un peu avant son expiration

# Plusieurs threads peuvent appeler ce module en même temps : le verrou les met à tour de rôle.
_lock = threading.Lock()

# state -> (session_id, échéance)
_pending_states: dict[str, tuple[str, float]] = {}
# session_id -> (jeton d'accès, échéance)
_tokens: dict[str, tuple[str, float]] = {}


def _purge_expired_states() -> None:
    """Retire les « state » périmés (à appeler avec le verrou déjà pris)."""
    now = time.monotonic()
    for key in [k for k, (_, expires_at) in _pending_states.items() if expires_at <= now]:
        del _pending_states[key]


def remember_state(state: str, session_id: str) -> None:
    """Retient quelle session a demandé la connexion Google."""
    with _lock:
        _purge_expired_states()
        _pending_states[state] = (session_id, time.monotonic() + STATE_LIFETIME_SECONDS)


def consume_state(received_state: str) -> str | None:
    """Retourne le session_id associé au « state » reçu, puis l'oublie (usage unique).

    Retourne None si le « state » est inconnu, déjà utilisé ou périmé.
    """
    with _lock:
        entry = _pending_states.pop(received_state, None)
    if entry is None:
        return None
    session_id, expires_at = entry
    return session_id if time.monotonic() < expires_at else None


def store_token(session_id: str, access_token: str, expires_in: int) -> None:
    """Range le jeton d'accès de cette session, avec une marge de sécurité."""
    lifetime = max(expires_in - TOKEN_SAFETY_MARGIN_SECONDS, 0)
    with _lock:
        _tokens[session_id] = (access_token, time.monotonic() + lifetime)


def get_token(session_id: str) -> str | None:
    """Retourne le jeton de la session, ou None s'il est absent ou périmé."""
    with _lock:
        entry = _tokens.get(session_id)
        if entry is None:
            return None
        access_token, expires_at = entry
        if time.monotonic() >= expires_at:
            del _tokens[session_id]
            return None
        return access_token


def discard_token(session_id: str) -> None:
    """Oublie le jeton (moindre privilège : après usage, on ne le garde pas)."""
    with _lock:
        _tokens.pop(session_id, None)


def clear_all() -> None:
    """Vide le registre : utile aux tests, pour qu'ils restent indépendants."""
    with _lock:
        _pending_states.clear()
        _tokens.clear()