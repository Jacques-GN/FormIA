"""Rendu texte de la proposition, produit par le code à partir du schéma validé.

Règle du projet : ce que l'utilisateur lit ne doit pas être rédigé librement par
le LLM. Le LLM propose une structure ; ce module la met en mots de façon
déterministe. Le texte affiché correspond donc exactement à la version qui sera
confirmée, puis créée.

Liens avec les autres fichiers
------------------------------
- schemas/form.py : fournit le Form déjà validé (aucune donnée non fiable ici).
- api/routes.py   : renvoie ce texte au client, qui l'affiche tel quel.
"""

from app.schemas.form import (
    CHOICE_TYPES,
    Form,
    Question,
    QuestionOrigin,
    QuestionType,
)

# Libellés lisibles des types, pour l'utilisateur (jamais les noms techniques).
TYPE_LABELS = {
    QuestionType.SHORT_TEXT: "réponse courte",
    QuestionType.PARAGRAPH: "paragraphe",
    QuestionType.MULTIPLE_CHOICE: "choix unique",
    QuestionType.CHECKBOXES: "cases à cocher",
    QuestionType.DROPDOWN: "liste déroulante",
}

# Rappel explicite : une proposition n'est jamais une validation.
NOT_CREATED_YET = (
    "Aucun formulaire n'a encore été créé : rien n'est envoyé à Google Forms "
    "avant votre confirmation."
)


def _question_block(position: int, question: Question) -> str:
    """Rend une question : intitulé, type, options et origine."""
    details = [TYPE_LABELS[question.type]]
    if question.required:
        details.append("obligatoire")
    lignes = [f"{position}. {question.title} ({', '.join(details)})"]

    if question.description:
        lignes.append(f"   {question.description}")

    if question.type in CHOICE_TYPES:
        lignes.extend(f"   - {option}" for option in question.options)

    if question.origin is QuestionOrigin.SUGGESTED:
        lignes.append(f"   Suggérée parce que : {question.justification}")
    else:
        lignes.append("   Demandée par vous.")

    return "\n".join(lignes)


def render_proposal(form: Form) -> str:
    """Met le formulaire en texte lisible, sans rien inventer."""
    blocs = [form.title]
    if form.description:
        blocs.append(form.description)
    blocs.extend(
        _question_block(position, question)
        for position, question in enumerate(form.questions, start=1)
    )
    blocs.append(NOT_CREATED_YET)
    return "\n\n".join(blocs)


def render_clarification(questions: list[str]) -> str:
    """Met les questions de clarification en texte, une par ligne."""
    lignes = ["J'ai besoin de quelques précisions pour un formulaire utile :"]
    lignes.extend(f"- {question}" for question in questions)
    return "\n".join(lignes)
