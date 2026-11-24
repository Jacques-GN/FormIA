"""Étapes (nœuds) du graphe LangGraph de Formia.

Un nœud reçoit l'état et retourne un dictionnaire des champs à modifier.
Il délègue le travail IA à services/form_generator.py et ne décide jamais
de la suite : c'est orchestrator.py qui choisit le chemin.

Liens : state.py (contrat de l'état), form_generator.py (appels au LLM),
orchestrator.py (assemble ces étapes en graphe).
"""

import json

from pydantic import ValidationError

from app.agents.intent_router import Intention
from app.agents.state import FormiaState
from app.services import form_generator


def analyser_demande(state: FormiaState) -> dict:
    """Première étape de chaque tour : le LLM dit s'il manque des informations.

    L'intention du routeur peut court-circuiter cette étape pour éviter un
    appel LLM inutile :
    - HORS_SUJET : pas d'appel LLM, la demande n'est pas traitée.
    - ANNULATION : on vide le formulaire en cours.
    """
    intention = state.get("intention")

    if intention == Intention.HORS_SUJET:
        return {
            "questions": [],
            "formulaire": {},
            "tentatives": 0,
            "erreur": "hors_sujet",
        }

    if intention == Intention.ANNULATION:
        return {
            "questions": [],
            "formulaire": {},
            "tentatives": 0,
            "erreur": "",
        }

    analyse = form_generator.analyze_request(state["historique"])
    return {
        "questions": analyse.questions,
        # Remise à zéro : l'état est conservé d'un message à l'autre.
        "formulaire": {},
        "tentatives": 0,
        "erreur": "",
    }


def poser_questions(state: FormiaState) -> dict:
    """Transforme les questions de clarification en message pour l'utilisateur."""
    texte = "\n".join(f"- {question}" for question in state["questions"])
    # operator.add sur « historique » : ce message est AJOUTÉ à la conversation.
    return {"historique": [{"role": "assistant", "content": texte}]}


def generer_formulaire(state: FormiaState) -> dict:
    """Demande le formulaire au LLM. En cas d'échec, note l'erreur pour la relance."""
    tentatives = state.get("tentatives", 0) + 1
    try:
        formulaire = form_generator.generate_form(
            state["historique"],
            previous_error=state.get("erreur", ""),
        )
    except ValidationError as erreur:
        # On ne relance pas ici : on enregistre, le graphe décidera.
        # Sécurité : ce texte sert au LLM, il ne doit jamais être montré au client.
        return {"erreur": str(erreur), "tentatives": tentatives}

    # mode="json" : types simples (le type de question devient un texte).
    formulaire_dict = formulaire.model_dump(mode="json")
    return {
        "formulaire": formulaire_dict,
        "erreur": "",
        "tentatives": tentatives,
        # Le formulaire entre dans la conversation : le LLM pourra le retrouver
        # quand l'utilisateur demandera une correction.
        "historique": [
            {
                "role": "assistant",
                "content": json.dumps(formulaire_dict, ensure_ascii=False),
            }
        ],
    }