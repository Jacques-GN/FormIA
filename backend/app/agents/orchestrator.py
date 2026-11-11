"""Construction et exécution du graphe de génération de formulaire."""

from collections.abc import Callable

from app.agents import edges, nodes
from app.agents.state import FormRequestState

Node = Callable[[FormRequestState], None]


def build_form_request_graph() -> tuple[dict[str, Node], str]:
    """Construit les étapes disponibles et indique le point de départ."""
    graph = {
        "validate_request": nodes.validate_request,
        "generate_form": nodes.generate_form,
    }
    return graph, "validate_request"


def orchestrate_form_request(prompt: str):
    """Lance les étapes du graphe et retourne le formulaire généré."""
    graph, current_node = build_form_request_graph()
    state = FormRequestState(prompt=prompt)

    while current_node is not None:
        node = graph.get(current_node)
        if node is None:
            raise RuntimeError(f"Étape inconnue dans le graphe : {current_node}")

        node(state)
        current_node = edges.next_step(current_node, state)

    if state.form is None:
        raise RuntimeError("Le graphe s'est terminé sans produire de formulaire.")

    return state.form
