"""Tests du service d'extraction de documents (parcours Direct).

Aucun appel réseau réel, aucun vrai fichier PDF/Word : tout est simulé.
"""

from pathlib import Path
from unittest import mock

import pytest

from app.services import document
from app.schemas.document import DocumentExtraction, ExtractedQuestion, SourceTrace
from app.schemas.form import QuestionType


def test_valider_fichier_refuse_fichier_inexistant():
    with pytest.raises(document.DocumentError):
        document.validate_file(Path("n'existe_pas.pdf"))


def test_valider_fichier_refuse_extension_incoherente(tmp_path):
    # Un fichier .exe avec un MIME pdf détecté (ici on force via monkeypatch)
    faux = tmp_path / "test.exe"
    faux.write_bytes(b"%PDF-1.4 fake")

    with mock.patch("mimetypes.guess_type", return_value=("application/pdf", None)):
        with pytest.raises(document.DocumentError):
            document.validate_file(faux)


def test_extraire_texte_pdf_sans_texte():
    """Un PDF sans texte extrait -> has_text=False."""
    avec_mock = mock.patch(
        "app.services.document.extract_text_from_pdf",
        return_value=("", 3),
    )
    with mock.patch.object(Path, "exists", return_value=True), mock.patch.object(
        Path, "stat", return_value=mock.Mock(st_size=1000)
    ), mock.patch("mimetypes.guess_type", return_value=("application/pdf", None)), \
         mock.patch.object(Path, "suffixes", [".pdf"]), avec_mock:
        result = document.extraire_questions_du_document(Path("faux.pdf"))

    assert result.has_text is False
    assert result.total_pages == 3
    assert result.questions == []


def test_extraire_questions_avec_source_trace():
    """Chaque question extraite porte une source (page, paragraphe, passage)."""
    texte = """--- Page 1 ---\nQuel est votre nom ?\n--- Page 2 ---\nQuel âge avez-vous ?"""

    with mock.patch.object(Path, "exists", return_value=True), mock.patch.object(
        Path, "stat", return_value=mock.Mock(st_size=1000)
    ), mock.patch("mimetypes.guess_type", return_value=("application/pdf", None)), \
         mock.patch.object(Path, "suffixes", [".pdf"]), \
         mock.patch(
             "app.services.document.extract_text_from_pdf",
             return_value=(texte, 2),
         ), \
         mock.patch(
             "app.services.form_generator.generate_completion",
             return_value='{"questions": [{"title": "Quel est votre nom ?", '
             '"type": "short_text", "required": true, "options": [], '
             '"source": {"page": 1, "paragraph": "", "passage": "Quel est votre nom ?"}, '
             '"confidence": 0.95}]}',
         ):
        result = document.extraire_questions_du_document(Path("faux.pdf"))

    assert result.has_text is True
    assert len(result.questions) == 1
    q = result.questions[0]
    assert q.title == "Quel est votre nom ?"
    assert q.source.page == 1
    assert q.source.passage == "Quel est votre nom ?"
    assert q.confidence == 0.95


def test_questions_sans_options_pour_texte_sont_refusees():
    """Une question de texte avec des options est ignorée (validation)."""
    avec_mock = mock.patch(
        "app.services.form_generator.generate_completion",
        return_value='{"questions": [{"title": "Nom", "type": "short_text", '
        '"options": ["A", "B"]}]}',
    )
    with mock.patch.object(Path, "exists", return_value=True), mock.patch.object(
        Path, "stat", return_value=mock.Mock(st_size=1000)
    ), mock.patch("mimetypes.guess_type", return_value=("application/pdf", None)), \
         mock.patch.object(Path, "suffixes", [".pdf"]), \
         mock.patch(
             "app.services.document.extract_text_from_pdf",
             return_value=("Quel est votre nom ?", 1),
         ), avec_mock:
        result = document.extraire_questions_du_document(Path("faux.pdf"))

    # La question invalide est ignorée, pas d'échec total.
    assert result.questions == []
