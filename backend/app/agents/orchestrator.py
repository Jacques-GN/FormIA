"""Assemblage du graphe LangGraph de Formia et point d'entrée de l'agent.

Liens : state.py (forme de l'état), nodes.py (les étapes), routes.py (appelle
traiter_message, seule fonction publique de ce fichier).
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents import nodes
from app.agents.state import FormiaState

# Nombre maximal de générations par message : évite une boucle sans fin
# (et des appels LLM coûteux) si le modèle produit toujours un JSON invalide.
MAX_TENTATIVES = 2


# --- Fonctions de routage : elles LISENT l'état et retournent une étiquette. ---


def apres_analyse(state: FormiaState) -> str:
    """Des questions à poser ? Sinon, on génère le formulaire."""
    return "clarifier" if state.get("questions") else "generer"


def apres_generation(state: FormiaState) -> str:
    """Formulaire valide : on termine. Sinon, on réessaie tant qu'il reste des essais."""
    if state.get("formulaire"):
        return "terminer"
    if state.get("tentatives", 0) < MAX_TENTATIVES:
        return "reessayer"
    return "terminer"  # plus d'essais : routes.py verra l'absence de formulaire


def construire_graphe():
    """Déclare les étapes et les chemins, puis compile le graphe avec sa mémoire."""
    builder = StateGraph(FormiaState)

    builder.add_node("analyser_demande", nodes.analyser_demande)
    builder.add_node("poser_questions", nodes.poser_questions)
    builder.add_node("generer_formulaire", nodes.generer_formulaire)

    builder.add_edge(START, "analyser_demande")

    # Étiquette retournée par la fonction -> nœud suivant.
    builder.add_conditional_edges(
        "analyser_demande",
        apres_analyse,
        {"clarifier": "poser_questions", "generer": "generer_formulaire"},
    )
    builder.add_edge("poser_questions", END)
    builder.add_conditional_edges(
        "generer_formulaire",
        apres_generation,
        {"terminer": END, "reessayer": "generer_formulaire"},
    )

    # Le checkpointer sauvegarde l'état après chaque étape, par thread_id.
    # En RAM : la mémoire est perdue au redémarrage du serveur (et non partagée
    # entre plusieurs processus). Une vraie base viendra après le MVP.
    return builder.compile(checkpointer=InMemorySaver())


# Compilé UNE fois au chargement : sinon la mémoire serait perdue à chaque requête.
graphe = construire_graphe()


def traiter_message(message: str, session_id: str) -> FormiaState:
    """Fait avancer la conversation d'un message et retourne l'état final.

    session_id : identifiant de la conversation. Même identifiant = même mémoire.
    """
    configuration = {"configurable": {"thread_id": session_id}}
    entree = {
        # operator.add : ce message est ajouté à l'historique déjà sauvegardé.
        "historique": [{"role": "user", "content": message}],
        "demande": message,
    }
    return graphe.invoke(entree, configuration)


def lire_etat(session_id: str) -> FormiaState:
    """Retourne l'état sauvegardé d'une session (vide si elle n'existe pas).

    Permet à routes.py de retrouver le formulaire d'une session sans toucher
    au graphe directement.
    """
    configuration = {"configurable": {"thread_id": session_id}}
    return graphe.get_state(configuration).values