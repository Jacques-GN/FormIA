"""Logique IA de Formia : quoi demander au LLM, et comment vérifier sa réponse.

Liens avec les autres fichiers
------------------------------
- agents/nodes.py   : appelle analyze_request() et generate_form().
- services/LLM.py   : envoie les messages au fournisseur (ce fichier n'y fait
                      aucun appel réseau lui-même).
- schemas/form.py   : fournit les modèles qui valident les réponses du LLM.

Ce fichier ne connaît pas LangGraph : il reçoit des messages et rend un résultat.
Sécurité : le texte de l'utilisateur est une entrée non fiable ; le LLM peut
seulement proposer, et c'est le schéma Pydantic qui décide si c'est valide.
"""

from app.schemas.form import Form, Modification, RequestAnalysis
from app.services.LLM import generate_completion

# Plafond d'historique envoyé au LLM : le coût doit rester borné même sur une
# longue conversation. On garde le premier message (le brief initial) et les
# plus récents ; l'état structuré du formulaire reste, lui, complet.
MAX_HISTORY_MESSAGES = 20

# Consignes de l'« analyste ». Le mot JSON y figure : certains fournisseurs
# l'exigent quand response_format vaut json_object (voir LLM.py).
ANALYSIS_PROMPT = """\
Tu analyses la demande d'un utilisateur qui veut créer un formulaire.
Décide s'il manque des informations ESSENTIELLES pour le concevoir
(par exemple : le sujet, le public visé, ou les informations à collecter).
Réponds uniquement avec un objet JSON valide de ce format :
{"questions": ["Question à poser à l'utilisateur"]}
- Si la demande est assez claire, réponds {"questions": []}.
- Pose au maximum 3 questions courtes, rédigées uniquement dans la langue de l'utilisateur (aucun mot d'une autre langue).
- Ne pose pas de question sur des détails que tu peux choisir toi-même.
"""

# Consignes du « concepteur ».
GENERATION_PROMPT = """\
Tu conçois des formulaires. Réponds uniquement avec un objet JSON valide
conforme à ce format :
{
  "title": "Titre du formulaire",
  "description": "Description facultative",
  "questions": [
    {
      "title": "Intitulé de la question",
      "description": "Précision facultative affichée sous la question",
      "type": "short_text",
      "required": false,
      "options": [],
      "origin": "user",
      "justification": ""
    }
  ]
}
Les types autorisés sont : short_text, paragraph, multiple_choice,
checkboxes et dropdown. Les questions à choix doivent avoir au moins deux
options. Les questions de texte ne doivent pas avoir d'options.

Chaque question porte une origine :
- "user" : l'utilisateur l'a demandée explicitement dans son brief.
- "suggested" : tu la proposes pour atteindre l'objectif du brief. Dans ce cas,
  "justification" explique en une phrase courte, dans la langue de
  l'utilisateur, en quoi cette question sert cet objectif.
Une question "suggested" sans justification est refusée.
N'invente pas de besoin : ne marque "user" que ce qui figure dans le brief.
Ne propose aucune question sur des données sensibles (santé, religion, opinions
politiques, identité) sans nécessité explicite.
Écris le formulaire dans la langue de l'utilisateur.
"""


def _bounded_history(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Réduit l'historique envoyé au fournisseur sans perdre le brief initial."""
    if len(messages) <= MAX_HISTORY_MESSAGES:
        return messages
    return [messages[0], *messages[-(MAX_HISTORY_MESSAGES - 1) :]]


def analyze_request(messages: list[dict[str, str]]) -> RequestAnalysis:
    """Demande au LLM s'il manque des informations essentielles.

    Retourne une RequestAnalysis : questions vide = on peut générer.
    Lève une ValidationError si la réponse du LLM n'est pas conforme.
    """
    response = generate_completion(_bounded_history(messages), system_prompt=ANALYSIS_PROMPT)
    return RequestAnalysis.model_validate_json(response)


def generate_form(messages: list[dict[str, str]], previous_error: str = "") -> Form:
    """Demande au LLM de concevoir le formulaire, puis valide sa réponse.

    previous_error : l'erreur de la tentative précédente, s'il y en a eu une.
    On la renvoie au LLM pour qu'il corrige sa réponse.
    Lève une ValidationError si le JSON est cassé ou non conforme au schéma Form.
    """
    if previous_error:
        messages = [
            *messages,
            {
                "role": "user",
                "content": (
                    f"Ta réponse précédente était invalide : {previous_error}\n"
                    "Corrige-la et réponds uniquement avec le JSON demandé."
                ),
            },
        ]

    response = generate_completion(
        _bounded_history(messages), system_prompt=GENERATION_PROMPT
    )
    return Form.model_validate_json(response)


# Consignes pour proposer une modification ciblée (§5 : opération ciblée,
# pas régénération complète non contrôlée).
MODIFICATION_PROMPT = """\
Tu proposes une modification ciblée sur un formulaire existant. Réponds
uniquement avec un objet JSON valide de ce format :
{
  "type": "ajouter" | "supprimer" | "modifier",
  "position": 3,
  "question": {
    "title": "Intitulé de la question",
    "description": "Précision facultative",
    "type": "short_text",
    "required": false,
    "options": [],
    "origin": "user",
    "justification": ""
  }
}
- "ajouter" : insère la question à la position donnée (question requise).
- "supprimer" : retire la question à la position donnée (question ignorée).
- "modifier" : remplace la question à la position donnée (question requise).
La position est 1-indexée (1 = première question).
N'invente pas de besoin : ne modifie que ce que l'utilisateur a demandé.
Écris dans la langue de l'utilisateur.
"""


def propose_modification(
    messages: list[dict[str, str]], previous_error: str = ""
) -> Modification:
    """Demande au LLM de proposer une modification ciblée du formulaire.

    Retourne une Modification validée par Pydantic. Le backend l'applique
    ensuite via form_operations (opération pure, pas de régénération complète).
    Lève une ValidationError si la réponse du LLM n'est pas conforme.
    """
    if previous_error:
        messages = [
            *messages,
            {
                "role": "user",
                "content": (
                    f"Ta réponse précédente était invalide : {previous_error}\n"
                    "Corrige-la et réponds uniquement avec le JSON demandé."
                ),
            },
        ]

    response = generate_completion(
        _bounded_history(messages), system_prompt=MODIFICATION_PROMPT
    )
    return Modification.model_validate_json(response)