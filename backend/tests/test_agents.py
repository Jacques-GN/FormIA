"""Tests du graphe de l'agent, avec un LLM simulé (aucun appel réseau)."""

from uuid import uuid4

from app.agents import nodes
from app.agents.orchestrator import MAX_TENTATIVES, traiter_message
from app.schemas.form import (
    Form,
    Modification,
    ModificationType,
    Question,
    QuestionType,
    RequestAnalysis,
)
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


def test_hors_sujet_n_appelle_pas_le_llm(monkeypatch):
    """Un message hors sujet ne doit pas déclencher d'appel LLM (coût zéro)."""
    analyse_appelee = {"compteur": 0}

    def analyse_surveillee(messages):
        analyse_appelee["compteur"] += 1
        return RequestAnalysis()

    def generate_bloque(*args, **kwargs):
        raise AssertionError(
            "generate_form ne doit pas être appelé pour un hors sujet"
        )

    monkeypatch.setattr(form_generator, "analyze_request", analyse_surveillee)
    monkeypatch.setattr(form_generator, "generate_form", generate_bloque)

    etat = traiter_message("Quel temps fait-il ?", nouvelle_session())

    assert analyse_appelee["compteur"] == 0
    assert etat.get("erreur") == "hors_sujet"
    assert not etat.get("questions")
    assert not etat.get("formulaire")


def test_annulation_vide_le_formulaire_en_cours(monkeypatch):
    """Annuler supprime le formulaire et les questions en cours."""
    monkeypatch.setattr(
        form_generator, "analyze_request", lambda messages: RequestAnalysis()
    )
    monkeypatch.setattr(
        form_generator, "generate_form", lambda *a, **k: FORMULAIRE
    )

    session = nouvelle_session()
    etat = traiter_message("Un formulaire d'inscription", session)
    assert etat.get("formulaire")

    etat = traiter_message("Annule tout", session)

    assert etat.get("formulaire") == {}
    assert etat.get("questions") == []
    assert etat.get("erreur") == ""


def test_modification_applique_operation_ciblee(monkeypatch):
    """Modification : le LLM propose une operation ciblee, le backend l'applique."""
    appele = {"compteur": 0}

    def propose(messages, previous_error=""):
        appele["compteur"] += 1
        return Modification(
            type=ModificationType.MODIFIER,
            position=1,
            question=Question(
                title="Nouvelle Q", type=QuestionType.SHORT_TEXT
            ),
        )

    monkeypatch.setattr(form_generator, "analyze_request", lambda m: RequestAnalysis())
    monkeypatch.setattr(
        form_generator,
        "generate_form",
        lambda messages, previous_error="": Form(
            title="Inscription",
            questions=[Question(title="Q1", type=QuestionType.SHORT_TEXT)],
        ),
    )
    monkeypatch.setattr(form_generator, "propose_modification", propose)

    session = nouvelle_session()
    traiter_message("Un formulaire d'inscription", session)
    appele["compteur"] = 0
    etat = traiter_message("Change la premiere question", session)

    assert appele["compteur"] == 1


def test_gerer_modification_directement(monkeypatch):
    """gerer_modification applique une operation via form_operations."""
    from app.agents import nodes
    from app.services import form_generator

    formule = Form(
        title="Test",
        questions=[Question(title="Q1", type=QuestionType.SHORT_TEXT)],
    ).model_dump(mode="json")

    etat = {
        "historique": [{"role": "user", "content": "Change la question"}],
        "formulaire": formule,
        "questions": [],
        "tentatives": 0,
        "erreur": "",
    }

    mod = Modification(
        type=ModificationType.MODIFIER,
        position=1,
        question=Question(title="Nouvelle Q", type=QuestionType.SHORT_TEXT),
    )
    monkeypatch.setattr(form_generator, "propose_modification", lambda *a, **k: mod)
    res = nodes.gerer_modification(etat)

    assert res["erreur"] == ""
    assert res["formulaire"]["questions"][0]["title"] == "Nouvelle Q"


def test_justification_affiche_origine_des_questions(monkeypatch):
    """Demande de justification : affiche origine et justification suggeree."""
    monkeypatch.setattr(form_generator, "analyze_request", lambda m: RequestAnalysis())

    formule = {
        "title": "Test",
        "questions": [
            {"title": "Nom", "type": "short_text", "origin": "user"},
            {
                "title": "Age",
                "type": "short_text",
                "origin": "suggested",
                "justification": "pour adapter les groupes",
            },
        ],
    }
    etat = nodes.gerer_justification(
        {
            "intention": "demande_justification",
            "formulaire": formule,
            "questions": [],
            "tentatives": 0,
            "erreur": "",
        }
    )

    texte = etat["historique"][0]["content"]
    assert "suggérée : pour adapter les groupes" in texte
    assert "demandée par vous" in texte