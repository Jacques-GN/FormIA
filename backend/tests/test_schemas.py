"""Tests des modèles de données de Formia."""

import pytest
from pydantic import ValidationError

from app.schemas.form import Form, Question, QuestionOrigin, QuestionType

# ---------- Cas qui doivent réussir ----------


def test_text_question_is_valid():
    question = Question(title="Nom complet", type=QuestionType.SHORT_TEXT)
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


def test_une_question_suggeree_doit_etre_justifiee():
    with pytest.raises(ValidationError):
        Question(
            title="Âge ?",
            type=QuestionType.SHORT_TEXT,
            origin=QuestionOrigin.SUGGESTED,
        )


def test_une_justification_sans_origine_devient_une_suggestion():
    question = Question.model_validate(
        {
            "title": "Âge ?",
            "type": "short_text",
            "justification": "pour adapter la taille des groupes",
        }
    )

    assert question.origin is QuestionOrigin.SUGGESTED


def test_une_question_demandee_n_exige_pas_de_justification():
    question = Question(title="Nom", type=QuestionType.SHORT_TEXT)

    assert question.origin is QuestionOrigin.USER
    assert question.justification == ""


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


# ---------- Normalisation des types (alias) ----------


def test_type_alias_text_est_normalise_en_short_text():
    question = Question(title="Nom", type="text")
    assert question.type is QuestionType.SHORT_TEXT


def test_type_alias_radio_est_normalise_en_multiple_choice():
    question = Question(title="Choix", type="radio", options=["A", "B"])
    assert question.type is QuestionType.MULTIPLE_CHOICE


def test_type_alias_paragraph_est_normalise():
    question = Question(title="Details", type="long_answer")
    assert question.type is QuestionType.PARAGRAPH
