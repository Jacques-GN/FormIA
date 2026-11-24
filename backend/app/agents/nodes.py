"""Étapes (nœuds) du graphe LangGraph de Formia.

Chaque nœud reçoit l'état et retourne les champs à modifier.
orchestrator.py choisit le chemin suivant.

Liens : state.py (contrat), form_generator.py (appels LLM),
form_operations.py (modifications ciblées), orchestrator.py (assemblage).
"""

import json

from pydantic import ValidationError

from app.agents.intent_router import Intention, normaliser_intention
from app.agents.state import FormiaState
from app.schemas.form import Form
from app.services import form_generator, form_operations


def analyser_demande(state: FormiaState) -> dict:
    """Nouvelle idée ou ajout de contexte : le LLM dit s'il manque des infos."""
    intention = normaliser_intention(state.get("intention"))

    if intention == Intention.HORS_SUJET:
        return {"questions": [], "formulaire": {}, "tentatives": 0, "erreur": "hors_sujet"}

    if intention == Intention.ANNULATION:
        return {"questions": [], "formulaire": {}, "tentatives": 0, "erreur": ""}

    if intention in {Intention.MODIFICATION, Intention.DEMANDE_JUSTIFICATION}:
        # Géré par d'autres nœuds : rien à faire ici.
        return {}

    analyse = form_generator.analyze_request(state["historique"])
    return {
        "questions": analyse.questions,
        "formulaire": {},
        "tentatives": 0,
        "erreur": "",
    }


def poser_questions(state: FormiaState) -> dict:
    """Transforme les questions de clarification en message pour l'utilisateur."""
    texte = "\n".join(f"- {q}" for q in state["questions"])
    return {"historique": [{"role": "assistant", "content": texte}]}


def generer_formulaire(state: FormiaState) -> dict:
    """Demande le formulaire au LLM. Relance en cas d'erreur de validation."""
    tentatives = state.get("tentatives", 0) + 1
    try:
        formulaire = form_generator.generate_form(
            state["historique"], previous_error=state.get("erreur", "")
        )
    except ValidationError as erreur:
        return {"erreur": str(erreur), "tentatives": tentatives}

    formulaire_dict = formulaire.model_dump(mode="json")
    return {
        "formulaire": formulaire_dict,
        "erreur": "",
        "tentatives": tentatives,
        "historique": [
            {"role": "assistant", "content": json.dumps(formulaire_dict, ensure_ascii=False)}
        ],
    }


def gerer_modification(state: FormiaState) -> dict:
    """Modification ciblée : le LLM propose une opération, le backend l'applique.

    Lien : form_generator.propose_modification (LLM) -> form_operations (backend
    pur, pas de régénération complète).
    """
    tentatives = state.get("tentatives", 0) + 1
    try:
        modification = form_generator.propose_modification(
            state["historique"], previous_error=state.get("erreur", "")
        )
    except ValidationError as erreur:
        return {"erreur": str(erreur), "tentatives": tentatives}

    formule = state.get("formulaire")
    if not formule:
        return {"erreur": "Aucun formulaire à modifier.", "tentatives": tentatives}

    try:
        form = Form.model_validate(formule)
        if modification.type.value == "ajouter":
            form = form_operations.ajouter_question(
                form, modification.question, modification.position
            )
        elif modification.type.value == "supprimer":
            form = form_operations.supprimer_question(form, modification.position)
        elif modification.type.value == "modifier":
            form = form_operations.modifier_question(
                form, modification.position, modification.question
            )
    except Exception as erreur:
        return {"erreur": str(erreur), "tentatives": tentatives}

    formulaire_dict = form.model_dump(mode="json")
    return {
        "formulaire": formulaire_dict,
        "erreur": "",
        "tentatives": tentatives,
        "historique": [
            {
                "role": "assistant",
                "content": f"Modification appliquée : {modification.type.value} à la position {modification.position}.",
            }
        ],
    }


def gerer_justification(state: FormiaState) -> dict:
    """Affiche l'origine et la justification de chaque question suggérée."""
    formule = state.get("formulaire")
    if not formule:
        return {"message": "Aucun formulaire à commenter."}

    lignes = []
    for i, q in enumerate(formule.get("questions", []), start=1):
        origine = q.get("origin", "user")
        just = q.get("justification", "")
        if origine == "suggested" and just:
            lignes.append(f"{i}. {q['title']} — suggérée : {just}")
        else:
            lignes.append(f"{i}. {q['title']} — demandée par vous.")

    texte = "\n".join(lignes) if lignes else "Aucune question suggérée."
    return {"historique": [{"role": "assistant", "content": texte}]}
