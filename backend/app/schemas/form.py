"""Schémas Pydantic qui décrivent la structure d'un formulaire valide."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class QuestionType(str, Enum):
    """Les types de questions acceptés dans le MVP."""

    SHORT_TEXT = "short_text"
    PARAGRAPH = "paragraph"
    MULTIPLE_CHOICE = "multiple_choice"
    CHECKBOXES = "checkboxes"
    DROPDOWN = "dropdown"


class QuestionOrigin(str, Enum):
    """D'où vient une question : du brief, ou d'une suggestion de FormIA.

    Règle du produit : une question suggérée doit toujours porter une
    justification reliée à l'objectif annoncé par l'utilisateur. Une question
    « demandée par vous » découle directement de sa demande.
    """

    USER = "user"
    SUGGESTED = "suggested"


# Les types qui ont besoin d'une liste d'options.
CHOICE_TYPES = {
    QuestionType.MULTIPLE_CHOICE,
    QuestionType.CHECKBOXES,
    QuestionType.DROPDOWN,
}


# Mapping des variantes de type vers les types canoniques FormIA.
# Inspiré de hossein-haeri/google-form-builder (normalize_type).
TYPE_ALIASES = {
    "text": QuestionType.SHORT_TEXT,
    "short_text": QuestionType.SHORT_TEXT,
    "short_answer": QuestionType.SHORT_TEXT,
    "long_text": QuestionType.PARAGRAPH,
    "paragraph": QuestionType.PARAGRAPH,
    "long_answer": QuestionType.PARAGRAPH,
    "textarea": QuestionType.PARAGRAPH,
    "radio": QuestionType.MULTIPLE_CHOICE,
    "multiple_choice": QuestionType.MULTIPLE_CHOICE,
    "select": QuestionType.DROPDOWN,
    "dropdown": QuestionType.DROPDOWN,
    "checkbox": QuestionType.CHECKBOXES,
    "checkboxes": QuestionType.CHECKBOXES,
    "multi_select": QuestionType.CHECKBOXES,
}


class Question(BaseModel):
    """Une question du formulaire."""

    title: str = Field(min_length=1, max_length=300)
    type: QuestionType
    required: bool = False
    options: list[str] = Field(default_factory=list)

    # Précision affichée sous l'intitulé dans Google Forms.
    description: str = Field(default="", max_length=500)

    # Traçabilité : d'où vient la question et pourquoi elle existe.
    # Ces deux champs restent côté FormIA : ils ne sont jamais envoyés à Google.
    origin: QuestionOrigin = QuestionOrigin.USER
    justification: str = Field(default="", max_length=300)

    @model_validator(mode="before")
    @classmethod
    def infer_suggested_origin(cls, data):
        """Une justification sans origine explicite signifie une suggestion.

        Cela évite d'afficher « Demandée par vous » sur une question que le
        modèle a en réalité inventée pour compléter le brief.
        """
        if isinstance(data, dict):
            if not data.get("origin") and data.get("justification"):
                return {**data, "origin": QuestionOrigin.SUGGESTED}
        return data

    @field_validator("type", mode="before")
    @classmethod
    def normaliser_type(cls, valeur):
        """Accepte les variantes de type (ex: 'text', 'radio') et les normalize."""
        if isinstance(valeur, str):
            cle = valeur.strip().lower()
            if cle in TYPE_ALIASES:
                return TYPE_ALIASES[cle]
        return valeur

    @model_validator(mode="after")
    def check_options_match_type(self):
        """Vérifie que les options sont cohérentes avec le type de question."""

        if self.type in CHOICE_TYPES and len(self.options) < 2:
            raise ValueError("Une question à choix doit avoir au moins 2 options.")
        if self.type not in CHOICE_TYPES and self.options:
            raise ValueError("Une question de texte ne doit pas avoir d'options.")
        return self

    @model_validator(mode="after")
    def check_suggested_question_is_justified(self):
        """Une suggestion sans justification ne doit pas être affichée."""

        if self.origin is QuestionOrigin.SUGGESTED and not self.justification.strip():
            raise ValueError(
                "Une question suggérée doit porter une justification liée à "
                "l'objectif du brief."
            )
        return self


class Form(BaseModel):
    """Un formulaire complet."""

    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    questions: list[Question] = Field(min_length=1, max_length=50)


class RequestAnalysis(BaseModel):
    """Résultat de l'analyse d'une demande par le LLM.

    questions vide    -> la demande est assez claire, on peut générer le formulaire.
    questions remplie -> il manque des informations, on les demande à l'utilisateur.
    """

    # max_length=3 : on évite d'accabler l'utilisateur de questions.
    questions: list[str] = Field(default_factory=list, max_length=3)


class ModificationType(str, Enum):
    """Type d'opération ciblée sur le formulaire."""

    AJOUTER = "ajouter"
    SUPPRIMER = "supprimer"
    MODIFIER = "modifier"


class Modification(BaseModel):
    """Opération ciblée sur une question du formulaire.

    Le LLM propose l'opération ; le backend l'applique via form_operations.
    """

    type: ModificationType
    position: int = Field(ge=1, description="Position 1-indexée de la question")
    question: Question | None = None  # requis pour AJOUTER et MODIFIER

    @model_validator(mode="after")
    def check_question_when_required(self):
        """Une question est obligatoire pour ajouter ou modifier."""
        if self.type in {ModificationType.AJOUTER, ModificationType.MODIFIER}:
            if self.question is None:
                raise ValueError(
                    f"Une question est requise pour l'opération {self.type}."
                )
        return self
