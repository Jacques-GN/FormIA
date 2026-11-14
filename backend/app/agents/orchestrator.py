"""Construction et exécution du graphe LangGraph de génération de formulaire."""

from langgraph.graph import END, START, StateGraph

from app.agents import nodes
from app.agents.state import FormRequestState
from app.schemas.form import Form


def build_form_request_graph():
    """Déclare les étapes (nœuds) et leur ordre (arêtes), puis compile le graphe."""
    builder = StateGraph(FormRequestState)

    builder.add_node("validate_request", nodes.validate_request)
    builder.add_node("generate_form", nodes.generate_form)

    builder.add_edge(START, "validate_request")
    builder.add_edge("validate_request", "generate_form")
    builder.add_edge("generate_form", END)

    return builder.compile()


def orchestrate_form_request(prompt: str) -> Form:
    """Lance le graphe et retourne le formulaire généré."""
    graph = build_form_request_graph()
    result = graph.invoke(FormRequestState(prompt=prompt))

    # Selon le type d'état, invoke() renvoie un dict ou un objet : on gère les deux.
    form = result["form"] if isinstance(result, dict) else result.form
    if form is None:
        raise RuntimeError("Le graphe s'est terminé sans produire de formulaire.")
    return form