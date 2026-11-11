"""Tests des modèles de données de Formia."""

import pytest
from pydantic import ValidationError

from app.Models import Form, Question, QuestionType


# ---------- Cas qui doivent réussir ----------

def test_text_question_is_valid():
    question = Question(title="Nom complet", type=QuestionType.SHORT_TEXT )
    assert question.title == "Nom complet"
    assert question.required is False  # valeur par défaut


def test_choice_question_with_options_is_valid():
    question = Question(
        title="Niveau d'étude",
        type=QuestionType.DROPDOWN,
        options=["Licence", "Master"],
    )
    assert len(question.options) == 2


def test_form_with_one_question_is_valid():
    form = Form(
        title="Inscription IA",
        questions=[{"title": "Nom complet", "type": "short_text"}], 
    )
    assert form.title == "Inscription IA"


# ---------- Cas qui doivent être refusés ----------

def test_choice_question_without_options_is_refused():
    with pytest.raises(ValidationError):
        Question(title="Niveau ?", type=QuestionType.DROPDOWN)


def test_choice_question_with_one_option_is_refused():
    with pytest.raises(ValidationError):
        Question(title="Niveau ?", type=QuestionType.CHECKBOXES, options=["Licence"])


def test_text_question_with_options_is_refused():
    with pytest.raises(ValidationError):
        Question(title="Nom ?", type=QuestionType.SHORT_TEXT, options=["A", "B"])


def test_unknown_question_type_is_refused():
    with pytest.raises(ValidationError):
        Question(title="Test", type="chocolat")


def test_empty_title_is_refused():
    with pytest.raises(ValidationError):
        Question(title="", type=QuestionType.SHORT_TEXT)


def test_form_without_questions_is_refused():
    with pytest.raises(ValidationError):
        Form(title="Formulaire vide", questions=[])