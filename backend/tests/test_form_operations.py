"""Tests des opérations ciblées sur la structure d'un formulaire."""

from app.schemas.form import Form, Question, QuestionType
from app.services import form_operations

FORM = Form(
    title="Test",
    questions=[
        Question(title="Q1", type=QuestionType.SHORT_TEXT),
        Question(title="Q2", type=QuestionType.SHORT_TEXT),
    ],
)


def test_ajouter_question_a_la_fin():
    resultat = form_operations.ajouter_question(
        FORM, Question(title="Q3", type=QuestionType.SHORT_TEXT)
    )
    assert len(resultat.questions) == 3
    assert resultat.questions[2].title == "Q3"


def test_ajouter_question_a_une_position():
    resultat = form_operations.ajouter_question(
        FORM, Question(title="Q1bis", type=QuestionType.SHORT_TEXT), position=1
    )
    assert len(resultat.questions) == 3
    assert resultat.questions[1].title == "Q1bis"
    assert resultat.questions[2].title == "Q2"


def test_supprimer_question():
    resultat = form_operations.supprimer_question(FORM, 1)
    assert len(resultat.questions) == 1
    assert resultat.questions[0].title == "Q2"


def test_supprimer_position_invalide_ne_change_rien():
    resultat = form_operations.supprimer_question(FORM, 99)
    assert len(resultat.questions) == 2


def test_modifier_question():
    resultat = form_operations.modifier_question(
        FORM, 2, Question(title="Q2 modifiee", type=QuestionType.PARAGRAPH)
    )
    assert len(resultat.questions) == 2
    assert resultat.questions[1].title == "Q2 modifiee"
    assert resultat.questions[1].type == QuestionType.PARAGRAPH


def test_definir_titre_et_description():
    resultat = form_operations.definir_titre(FORM, "Nouveau titre")
    assert resultat.title == "Nouveau titre"
    assert resultat.description == FORM.description

    resultat = form_operations.definir_description(resultat, "Desc")
    assert resultat.description == "Desc"


def test_formulaire_original_inchange():
    form_operations.modifier_question(FORM, 1, Question(title="X", type=QuestionType.SHORT_TEXT))
    assert FORM.questions[0].title == "Q1"
