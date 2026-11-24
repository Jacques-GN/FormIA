"""Opérations ciblées sur la structure d'un formulaire.

Toutes les fonctions sont pures : elles reçoivent un `Form` et en retournent
un nouveau, sans effet de bord. Utilisées par les noeuds de modification
(§5 : opérations ciblées, pas régénération complète non contrôlée).

Liens : schemas/form.py (modèle Form), agents/nodes.py (appelle ces fonctions).
"""

from app.schemas.form import Form, Question, QuestionType


def ajouter_question(form: Form, question: Question, position: int | None = None) -> Form:
    """Ajoute une question à la position donnée (ou à la fin)."""
    questions = list(form.questions)
    if position is None:
        questions.append(question)
    else:
        questions.insert(max(0, min(position, len(questions))), question)
    return form.model_copy(update={"questions": questions})


def supprimer_question(form: Form, position: int) -> Form:
    """Supprime la question à la position donnée (1-indexée)."""
    questions = list(form.questions)
    index = position - 1
    if 0 <= index < len(questions):
        questions.pop(index)
    return form.model_copy(update={"questions": questions})


def modifier_question(form: Form, position: int, question: Question) -> Form:
    """Remplace la question à la position donnée (1-indexée)."""
    questions = list(form.questions)
    index = position - 1
    if 0 <= index < len(questions):
        questions[index] = question
    return form.model_copy(update={"questions": questions})


def definir_titre(form: Form, titre: str) -> Form:
    """Définit le titre du formulaire."""
    return form.model_copy(update={"title": titre})


def definir_description(form: Form, description: str) -> Form:
    """Définit la description du formulaire."""
    return form.model_copy(update={"description": description})
