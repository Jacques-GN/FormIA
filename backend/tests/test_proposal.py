"""Tests du rendu texte de la proposition.

Le texte affiché est produit par le code à partir du formulaire validé : il ne
peut donc pas s'écarter de ce qui sera confirmé puis créé.
"""

from app.schemas.form import Form, Question, QuestionOrigin, QuestionType
from app.services.proposal import (
    NOT_CREATED_YET,
    render_clarification,
    render_proposal,
)


def formulaire() -> Form:
    return Form(
        title="Inscription au tournoi",
        description="Merci de répondre avant vendredi.",
        questions=[
            Question(title="Nom complet", type=QuestionType.SHORT_TEXT, required=True),
            Question(
                title="Niveau",
                type=QuestionType.DROPDOWN,
                options=["Débutant", "Confirmé"],
                description="Votre niveau actuel.",
                origin=QuestionOrigin.SUGGESTED,
                justification="pour répartir les équipes de façon équilibrée",
            ),
        ],
    )


def test_la_proposition_suit_l_ordre_des_questions():
    texte = render_proposal(formulaire())

    assert texte.index("1. Nom complet") < texte.index("2. Niveau")


def test_la_proposition_affiche_le_type_l_obligation_et_les_options():
    texte = render_proposal(formulaire())

    assert "1. Nom complet (réponse courte, obligatoire)" in texte
    assert "2. Niveau (liste déroulante)" in texte
    assert "   - Débutant" in texte
    assert "   - Confirmé" in texte


def test_la_proposition_reprend_la_description_d_une_question():
    assert "Votre niveau actuel." in render_proposal(formulaire())


def test_chaque_question_porte_son_origine():
    texte = render_proposal(formulaire())

    assert "Demandée par vous." in texte
    assert "Suggérée parce que : pour répartir les équipes" in texte


def test_la_proposition_rappelle_qu_aucun_formulaire_n_est_cree():
    assert NOT_CREATED_YET in render_proposal(formulaire())


def test_les_questions_de_clarification_sont_mises_en_texte():
    texte = render_clarification(["Quel public ?", "Quelle date ?"])

    assert texte.count("\n- ") == 2
    assert "Quel public ?" in texte
    assert "Quelle date ?" in texte
