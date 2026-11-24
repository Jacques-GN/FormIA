"""Suivi des créations Google Forms : idempotence et reprise.

Pourquoi ce module
------------------
Créer un formulaire se fait en deux appels Google (création vide, puis ajout
des questions). Une panne entre les deux laisse un formulaire incomplet chez
Google. Ce registre retient l'état de l'opération, y compris le `form_id` dès
qu'il est reçu, pour reprendre sur le même formulaire au lieu d'en créer un
second.

Limite assumée : le registre est en RAM, comme la mémoire de l'agent. Il ne
survit pas au redémarrage et n'est pas partagé entre processus. La cible
PostgreSQL du Bloc C remplacera ce stockage sans changer l'interface publique.

Sécurité : aucun jeton Google n'est stocké ici, uniquement des identifiants de
formulaire et des états.
"""

import threading
from dataclasses import dataclass, replace
from enum import Enum


class CreationState(str, Enum):
    """États explicites d'une création Google (cf. AGENTS.md §7.2)."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    RETRYABLE_ERROR = "RETRYABLE_ERROR"
    FAILED = "FAILED"
    UNKNOWN_EXTERNAL_RESULT = "UNKNOWN_EXTERNAL_RESULT"


@dataclass(frozen=True)
class CreationRecord:
    """Photo d'une tentative de création, pour une session et une empreinte."""

    session_id: str
    form_hash: str
    state: CreationState
    form_id: str | None = None
    responder_url: str | None = None
    edit_url: str | None = None
    error: str | None = None


_lock = threading.Lock()
_records: dict[tuple[str, str], CreationRecord] = {}


def _key(session_id: str, form_hash: str) -> tuple[str, str]:
    return session_id, form_hash


def try_begin(session_id: str, form_hash: str) -> tuple[CreationRecord, str]:
    """Tente de démarrer une création, de façon atomique.

    Retourne (enregistrement, statut) avec statut valant :
    - "started"   : la création peut commencer (aucune ou précédent échec) ;
    - "completed" : déjà réussie, renvoyer le résultat mémorisé sans rappeler Google ;
    - "pending"   : une autre requête identique est en cours.

    Le verrou couvre la lecture ET l'écriture : deux clics simultanés ne
    peuvent pas créer deux formulaires.
    """
    key = _key(session_id, form_hash)
    with _lock:
        record = _records.get(key)
        if record is None:
            record = CreationRecord(session_id, form_hash, CreationState.PENDING)
        elif record.state is CreationState.COMPLETED:
            return record, "completed"
        elif record.state is CreationState.PROCESSING:
            return record, "pending"

        record = replace(record, state=CreationState.PROCESSING, error=None)
        _records[key] = record
        return record, "started"


def remember_form(session_id: str, form_hash: str, form_id: str) -> None:
    """Enregistre le `form_id` immédiatement après sa réception."""
    with _lock:
        record = _records.get(_key(session_id, form_hash))
        if record is None:
            return
        _records[_key(session_id, form_hash)] = replace(record, form_id=form_id)


def complete(
    session_id: str,
    form_hash: str,
    *,
    form_id: str,
    responder_url: str,
    edit_url: str,
) -> None:
    """Marque la création comme terminée et mémorise le résultat à renvoyer."""
    with _lock:
        record = _records.get(_key(session_id, form_hash))
        if record is None:
            record = CreationRecord(session_id, form_hash, CreationState.COMPLETED)
        _records[_key(session_id, form_hash)] = replace(
            record,
            state=CreationState.COMPLETED,
            form_id=form_id,
            responder_url=responder_url,
            edit_url=edit_url,
            error=None,
        )


def mark_retryable(session_id: str, form_hash: str, error: str) -> None:
    """Échec récupérable : le `form_id` éventuel est conservé pour la reprise."""
    with _lock:
        record = _records.get(_key(session_id, form_hash))
        if record is None:
            return
        _records[_key(session_id, form_hash)] = replace(
            record, state=CreationState.RETRYABLE_ERROR, error=error
        )


def mark_failed(session_id: str, form_hash: str, error: str) -> None:
    """Échec définitif de cette tentative."""
    with _lock:
        record = _records.get(_key(session_id, form_hash))
        if record is None:
            return
        _records[_key(session_id, form_hash)] = replace(
            record, state=CreationState.FAILED, error=error
        )


def get(session_id: str, form_hash: str) -> CreationRecord | None:
    """Retourne l'enregistrement courant, ou None."""
    with _lock:
        return _records.get(_key(session_id, form_hash))


def clear_all() -> None:
    """Vide le registre : utile aux tests."""
    with _lock:
        _records.clear()
