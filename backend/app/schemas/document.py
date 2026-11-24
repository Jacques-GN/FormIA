"""Schémas pour l'extraction de documents (parcours Direct).

Lien : services/document.py (extraction), nodes.py (utilisation),
schemas/form.py (Form, Question).
"""

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.schemas.form import QuestionType


class SourceTrace(BaseModel):
    """D'où vient une question extraite d'un document.

    Règle §4.4 : traçabilité à la source (page, paragraphe, passage).
    """

    page: int | None = None  # numéro de page (1-indexé)
    paragraph: str | None = ""  # identifiant du paragraphe
    passage: str | None = ""  # extrait du texte source


class ExtractedQuestion(BaseModel):
    """Question extraite d'un document, avec sa source."""

    title: str = Field(min_length=1, max_length=300)
    type: QuestionType
    required: bool = False
    options: list[str] = Field(default_factory=list)
    source: SourceTrace = Field(default_factory=SourceTrace)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    @model_validator(mode="after")
    def check_options_match_type(self):
        from app.schemas.form import CHOICE_TYPES

        if self.type in CHOICE_TYPES and len(self.options) < 2:
            raise ValueError("Une question à choix doit avoir au moins 2 options.")
        if self.type not in CHOICE_TYPES and self.options:
            raise ValueError("Une question de texte ne doit pas avoir d'options.")
        return self


class DocumentExtraction(BaseModel):
    """Résultat de l'extraction d'un document."""

    questions: list[ExtractedQuestion] = Field(default_factory=list)
    source_document: str  # nom du fichier
    total_pages: int
    has_text: bool  # True si du texte a pu être extrait
