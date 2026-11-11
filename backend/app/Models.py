"""Modèles de données de Formia : décrivent à quoi ressemble un formulaire valide."""

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class QuestionType(str, Enum):
    """Les types de questions acceptés dans le MVP."""

    SHORT_TEXT = "short_text"
    PARAGRAPH = "paragraph"
    MULTIPLE_CHOICE = "multiple_choice"
    CHECKBOXES = "checkboxes"
    DROPDOWN = "dropdown"


# Les types qui ont besoin d'une liste d'options.
CHOICE_TYPES = {
    QuestionType.MULTIPLE_CHOICE,
    QuestionType.CHECKBOXES,
    QuestionType.DROPDOWN,
}


class Question(BaseModel):
    """Une question du formulaire."""

    title: str = Field(min_length=1, max_length=300)
    type: QuestionType
    required: bool = False
    options: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_options_match_type(self):
        """Vérifie que les options sont cohérentes avec le type de question."""
        
        if self.type in CHOICE_TYPES and len(self.options) < 2:
            raise ValueError("Une question à choix doit avoir au moins 2 options.")
        if self.type not in CHOICE_TYPES and self.options:
            raise ValueError("Une question de texte ne doit pas avoir d'options.")
        return self


class Form(BaseModel):
    """Un formulaire complet."""

    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    questions: list[Question] = Field(min_length=1, max_length=50)