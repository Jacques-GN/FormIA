"""Tests du routeur d'intentions.

Ces tests sont déterministes (aucun LLM, aucun appel réseau). Ils servent de
référence pour vérifier que toute modification du routage ne régressionne pas
le comportement attendu.
"""

from app.agents.intent_router import (
    Intention,
    IntentRouter,
    ResultatRoutage,
)


def route(router: IntentRouter, message: str, **contexte) -> ResultatRoutage:
    return router.router(message, contexte if contexte else None)


def test_nouvelle_idee():
    r = IntentRouter()
    resultat = route(r, "Je veux créer un formulaire d'inscription")

    assert resultat.intention is Intention.NOUVELLE_IDEA
    assert resultat.confiance >= 0.5


def test_ajout_contexte_apres_clarification():
    r = IntentRouter()
    resultat = route(
        r, "En fait, c'est pour une association sportive", a_deja_clarifie=True
    )

    assert resultat.intention is Intention.AJOUT_CONTEXTE


def test_modification_ciblee():
    r = IntentRouter()
    resultat = route(
        r, "Change la question 3, elle est trop longue", a_formulaire_pret=True
    )

    assert resultat.intention is Intention.MODIFICATION


def test_demande_justification():
    r = IntentRouter()
    resultat = route(r, "Pourquoi as-tu suggéré la question sur l'âge ?")

    assert resultat.intention is Intention.DEMANDE_JUSTIFICATION


def test_validation_explicite_sans_contexte():
    # Sans un formulaire presente, on ne peut pas confirmer une version
    # exacte : c'est une nouvelle idee, pas une validation.
    r = IntentRouter()
    resultat = route(r, "Ok, c'est bon, cree le formulaire")

    assert resultat.intention is Intention.NOUVELLE_IDEA


def test_validation_explicite_avec_formulaire_pret():
    r = IntentRouter()
    resultat = route(
        r, "C'est parfait", en_attente_confirmation=True, a_formulaire_pret=True
    )

    assert resultat.intention is Intention.VALIDATION_EXPLICITE
    assert resultat.confiance >= 0.5


def test_annulation():
    r = IntentRouter()
    resultat = route(r, "Non, annule tout")

    assert resultat.intention is Intention.ANNULATION


def test_hors_sujet():
    r = IntentRouter()
    resultat = route(r, "Quel temps fait-il aujourd'hui ?")

    assert resultat.intention is Intention.HORS_SUJET


def test_chaine_vide_est_hors_sujet():
    r = IntentRouter()
    resultat = route(r, "")

    assert resultat.intention is Intention.HORS_SUJET


def test_resultat_contient_raisons_et_metadata():
    r = IntentRouter()
    resultat = route(r, "Je veux un formulaire d'inscription")

    assert isinstance(resultat, ResultatRoutage)
    assert isinstance(resultat.raisons, list)
    assert isinstance(resultat.metadata, dict)
    assert "scores" in resultat.metadata


def test_seuil_personnalisable_baisse_la_confiance_requise():
    r = IntentRouter(seuils={Intention.HORS_SUJET: 0.9})
    resultat = route(r, "blablabla inconnu")

    # Le seuil de HORS_SUJET est très haut, donc un message sans match tombe
    # potentiellement dans une autre catégorie si score > 0, sinon HORS_SUJET.
    assert resultat.intention in {
        Intention.HORS_SUJET,
        Intention.AJOUT_CONTEXTE,
    }


def test_message_trop_court_peut_rester_hors_sujet():
    r = IntentRouter()
    resultat = route(r, "oui")

    # "oui" est un mot de validation mais sans contexte de formulaire, le score
    # reste faible -> HORS_SUJET ou AJOUT_CONTEXTE selon le contexte.
    assert resultat.intention in {
        Intention.HORS_SUJET,
        Intention.VALIDATION_EXPLICITE,
        Intention.AJOUT_CONTEXTE,
    }
