"""Tests du suivi des créations : idempotence et reprise."""

from app.integrations.google_forms import creation_store
from app.integrations.google_forms.creation_store import CreationState


def test_deux_confirmations_simultanees_ne_demarrent_qu_une_fois():
    premier, statut = creation_store.try_begin("session-1", "a" * 64)
    second, statut_2 = creation_store.try_begin("session-1", "a" * 64)

    assert statut == "started"
    assert statut_2 == "pending"
    assert premier.state is CreationState.PROCESSING
    assert second.state is CreationState.PROCESSING


def test_une_creation_terminee_est_rejouee_sans_nouvel_appel():
    creation_store.try_begin("session-1", "a" * 64)
    creation_store.complete(
        "session-1",
        "a" * 64,
        form_id="form-1",
        responder_url="https://forms.gle/x",
        edit_url="https://docs.google.com/forms/d/form-1/edit",
    )

    record, statut = creation_store.try_begin("session-1", "a" * 64)

    assert statut == "completed"
    assert record.form_id == "form-1"
    assert record.state is CreationState.COMPLETED


def test_le_form_id_survit_a_un_echec_recuperable():
    creation_store.try_begin("session-1", "a" * 64)
    creation_store.remember_form("session-1", "a" * 64, "form-1")
    creation_store.mark_retryable("session-1", "a" * 64, "questions manquantes")

    record = creation_store.get("session-1", "a" * 64)

    assert record.state is CreationState.RETRYABLE_ERROR
    assert record.form_id == "form-1"

    record, statut = creation_store.try_begin("session-1", "a" * 64)
    assert statut == "started"
    assert record.form_id == "form-1"


def test_deux_empreintes_differentes_sont_independantes():
    creation_store.try_begin("session-1", "a" * 64)
    record, statut = creation_store.try_begin("session-1", "b" * 64)

    assert statut == "started"
    assert record.form_hash == "b" * 64
