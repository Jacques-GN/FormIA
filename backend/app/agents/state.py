"""État partagé de l'agent Formia : la « mémoire de travail » d'une conversation.

Rôle de ce fichier
------------------
Un graphe LangGraph est une suite d'étapes. Pour qu'elles collaborent, elles
partagent un même objet : l'état. Ce fichier décrit ce que cet état contient.

Liens avec les autres fichiers
------------------------------
- agents/nodes.py        : chaque étape LIT l'état, puis retourne les champs
                           qu'elle modifie (un dictionnaire partiel).
- agents/orchestrator.py : donne FormiaState à StateGraph(...) pour construire
                           le graphe.
- api/routes.py          : fournit l'état de départ (la demande de l'utilisateur).
- schemas/form.py        : valide le contenu du champ « formulaire ».

Ce fichier n'importe aucun autre fichier du projet : il se lit et se comprend seul.
"""

import operator
from typing import Annotated, TypedDict


class FormiaState(TypedDict, total=False):
    """Données qui circulent entre les étapes du graphe.

    TypedDict : un dictionnaire dont on déclare les clés et leurs types.
    Python ne vérifie rien à l'exécution : c'est une documentation précise,
    que l'éditeur et LangGraph comprennent.

    total=False : toutes les clés sont optionnelles. Au début d'une conversation,
    seule la demande existe ; le reste est rempli par les étapes.

    Règle de fusion de LangGraph : quand une étape retourne {"champ": valeur},
    la nouvelle valeur REMPLACE l'ancienne... sauf si le champ a un « reducer »
    (voir « historique »).

    On utilise des types simples (texte, nombres, listes, dictionnaires) car
    l'état sera sauvegardé pour garder la mémoire d'une conversation, et ces
    types se sauvegardent sans difficulté.
    """

    # Seul champ avec un reducer : Annotated[type, fonction_de_fusion].
    # operator.add appliqué à deux listes les met bout à bout :
    #   ["a"] + ["b"]  ->  ["a", "b"]
    # Ainsi chaque étape AJOUTE des messages sans effacer les précédents.
    # Chaque message a le format {"role": "user" ou "assistant", "content": "..."},
    # le même que celui attendu par les API compatibles OpenAI (voir services/LLM.py).
    historique: Annotated[list[dict[str, str]], operator.add]

    # La demande actuelle de l'utilisateur (remplacée à chaque nouveau message).
    demande: str

    # Questions de clarification posées par l'agent quand il manque des
    # informations (ex. : « Combien de personnes sont attendues ? »).
    questions: list[str]

    # Le formulaire généré, sous forme de dictionnaire. On le valide avec le
    # schéma Form (schemas/form.py) avant de le considérer comme correct.
    formulaire: dict

    # Nombre de générations déjà essayées : sert à limiter les relances
    # automatiques quand le LLM produit un formulaire invalide.
    tentatives: int

    # Dernière erreur de validation. Elle peut être renvoyée au LLM pour
    # qu'il corrige sa réponse à la tentative suivante.
    erreur: str

    # Intention détectée par le routeur pour ce tour de conversation.
    # Valeurs : voir app.agents.intent_router.Intention.
    intention: str