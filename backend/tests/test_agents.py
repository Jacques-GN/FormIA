"""Tests du graphe de l'agent, avec un LLM simulé (aucun appel réseau)."""

from uuid import uuid4

from app.agents.orchestrator import MAX_TENTATIVES, traiter_message
from app.schemas.form import Form, Question, QuestionType, RequestAnalysis
from app.services import form_generator

FORMULAIRE = Form(
    title="Tournoi",
    questions=[Question(title="Nom", type=QuestionType.SHORT_TEXT)],
)


def nouvelle_session() -> str:
    # Un identifiant neuf par test : la mémoire du graphe est partagée.
    return str(uuid4())


def test_demande_incomplete_declenche_une_clarification(monkeypatch):
    monkeypatch.setattr(
        form_generator,
        "analyze_request",
        lambda messages: RequestAnalysis(questions=["Quel public ?"]),
    )

    def ne_doit_pas_etre_appele(*args, **kwargs):
        raise AssertionError("generate_form ne doit pas être appelé")

    monkeypatch.setattr(form_generator, "generate_form", ne_doit_pas_etre_appele)

    etat = traiter_message("Un formulaire", nouvelle_session())

    assert etat["questions"] == ["Quel public ?"]
    assert not etat.get("formulaire")
    assert etat["historique"][-1]["role"] == "assistant"


def test_demande_claire_genere_un_formulaire(monkeypatch):
    monkeypatch.setattr(
        form_generator, "analyze_request", lambda messages: RequestAnalysis()
    )
    monkeypatch.setattr(
        form_generator,
        "generate_form",
        lambda messages, previous_error="": FORMULAIRE,
    )

    etat = traiter_message("Un formulaire de tournoi", nouvelle_session())

    assert etat["formulaire"]["title"] == "Tournoi"
    assert etat["tentatives"] == 1


def test_relance_apres_une_reponse_invalide(monkeypatch):
    monkeypatch.setattr(
        form_generator, "analyze_request", lambda messages: RequestAnalysis()
    )
    erreurs_recues = []

    def generation(messages, previous_error=""):
        erreurs_recues.append(previous_error)
        if len(erreurs_recues) == 1:
            return Form.model_validate({})  # lève une ValidationError
        return FORMULAIRE

    monkeypatch.setattr(form_generator, "generate_form", generation)

    etat = traiter_message("Un formulaire", nouvelle_session())

    assert etat["tentatives"] == 2
    assert etat["formulaire"]["title"] == "Tournoi"
    assert erreurs_recues[0] == ""  # première tentative : aucune erreur
    assert erreurs_recues[1] != ""  # la seconde reçoit l'erreur de la première


def test_abandon_apres_le_maximum_de_tentatives(monkeypatch):
    monkeypatch.setattr(
        form_generator, "analyze_request", lambda messages: RequestAnalysis()
    )

    def toujours_invalide(messages, previous_error=""):
        return Form.model_validate({})

    monkeypatch.setattr(form_generator, "generate_form", toujours_invalide)

    etat = traiter_message("Un formulaire", nouvelle_session())

    assert not etat.get("formulaire")
    assert etat["tentatives"] == MAX_TENTATIVES
    assert etat["erreur"]


def test_la_session_garde_l_historique_et_reste_isolee(monkeypatch):
    monkeypatch.setattr(
        form_generator,
        "analyze_request",
        lambda messages: RequestAnalysis(questions=["Précisez ?"]),
    )
    session = nouvelle_session()

    traiter_message("Premier message", session)
    etat = traiter_message("Deuxième message", session)
    autre_etat = traiter_message("Autre conversation", nouvelle_session())

    def messages_utilisateur(resultat):
        return [m["content"] for m in resultat["historique"] if m["role"] == "user"]

    assert messages_utilisateur(etat) == ["Premier message", "Deuxième message"]
    assert messages_utilisateur(autre_etat) == ["Autre conversation"]