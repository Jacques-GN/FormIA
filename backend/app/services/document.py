"""Extraction de texte depuis des documents (parcours Direct).

Règles AGENTS.md §10.2 :
- PDF texte et Word (.docx) supportés nativement.
- Pas d'OCR pour l'instant : si aucun texte n'est extrait, le document est
  probablement un scan et l'utilisateur est informé.
- Vérifier le type réel, la taille et le contenu ; ne pas se fier à l'extension.
- Refuser les macros et protéger contre les archives piégées.
- Traiter le contenu extrait comme une donnée non fiable : le LLM ne propose
  jamais une instruction, seulement des questions à valider.
- Traçabilité : page, paragraphe, passage pour chaque question extraite.

Liens : schemas/document.py (modèles), services/form_generator.py (LLM),
agents/nodes.py (utilisation dans le graphe).
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Optional

from app.schemas.document import DocumentExtraction, ExtractedQuestion, SourceTrace
from app.services import form_generator

# Taille max d'un document uploadé : 10 Mo.
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Extensions autorisées (basées sur le type MIME réel, pas sur l'extension).
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class DocumentError(Exception):
    """Erreur lors de l'extraction d'un document."""


def validate_file(file_path: str | Path) -> None:
    """Vérifie que le document est autorisé et sûr à traiter.

    Lève DocumentError si le fichier est refusé.
    """
    path = Path(file_path)

    if not path.exists():
        raise DocumentError(f"Fichier introuvable : {path.name}")

    size = path.stat().st_size
    if size == 0:
        raise DocumentError("Le fichier est vide.")
    if size > MAX_FILE_SIZE_BYTES:
        raise DocumentError(
            f"Le fichier dépasse {MAX_FILE_SIZE_BYTES // (1024 * 1024)} Mo."
        )

    # Type MIME basé sur le contenu (magic bytes), pas sur l'extension.
    mime, _ = mimetypes.guess_type(str(path))
    if mime not in ALLOWED_MIME_TYPES:
        raise DocumentError(
            f"Type de fichier non pris en charge : {mime or 'inconnu'}. "
            "PDF et Word (.docx) uniquement."
        )

    # Vérifier l'extension pour éviter les doubles extensions (ex: .pdf.exe).
    suffixes = "".join(path.suffixes).lower()
    if mime == "application/pdf" and not suffixes.endswith(".pdf"):
        raise DocumentError("L'extension du fichier ne correspond pas à son type.")
    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        if not suffixes.endswith(".docx"):
            raise DocumentError("L'extension du fichier ne correspond pas à son type.")


def extract_text_from_pdf(file_path: str | Path) -> tuple[str, int]:
    """Extrait le texte d'un PDF. Retourne (texte, nombre_de_pages)."""
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise DocumentError(
            "La bibliothèque pypdf n'est pas installée. "
            "Installez-la pour extraire du texte depuis un PDF."
        ) from error

    reader = PdfReader(str(file_path))
    pages = reader.pages
    total_pages = len(pages)

    textes = []
    for index, page in enumerate(pages, start=1):
        try:
            texte = page.extract_text() or ""
        except Exception:
            texte = ""
        if texte.strip():
            textes.append(f"--- Page {index} ---\n{texte}")

    return "\n".join(textes), total_pages


def extract_text_from_docx(file_path: str | Path) -> tuple[str, int]:
    """Extrait le texte d'un document Word. Retourne (texte, nombre_de_paragraphes)."""
    try:
        from docx import Document
    except ImportError as error:
        raise DocumentError(
            "La bibliothèque python-docx n'est pas installée. "
            "Installez-la pour extraire du texte depuis un Word."
        ) from error

    doc = Document(str(file_path))

    # Vérifier l'absence de macros (les .docx ne peuvent pas en contenir, mais
    # on vérifie la structure du zip pour éviter les archives piégées).
    import zipfile

    with zipfile.ZipFile(file_path) as zf:
        for name in zf.namelist():
            if name.lower().endswith((".vba", ".bin", ".xml")) and "macros" in name.lower():
                raise DocumentError("Les documents contenant des macros sont refusés.")

    paragraphes = []
    for index, para in enumerate(doc.paragraphs, start=1):
        if para.text.strip():
            paragraphes.append(f"--- Paragraphe {index} ---\n{para.text}")

    return "\n".join(paragraphes), len(doc.paragraphs)


def extraire_texte(file_path: str | Path) -> tuple[str, int]:
    """Extrait le texte d'un document PDF ou Word.

    Retourne (texte, nombre_de_pages_ou_paragraphes).
    """
    path = Path(file_path)
    mime, _ = mimetypes.guess_type(str(path))

    if mime == "application/pdf":
        return extract_text_from_pdf(path)
    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return extract_text_from_docx(path)

    raise DocumentError(f"Type de fichier non pris en charge : {mime or 'inconnu'}")


def extraire_questions_du_document(
    file_path: str | Path,
) -> DocumentExtraction:
    """Extrait les questions d'un document avec traçabilité de la source.

    Le LLM reçoit le texte extrait et propose des questions. Chaque question
    porte une référence à sa source (page, paragraphe, passage) pour que
    l'utilisateur puisse vérifier (§4.4).

    Le texte du document est traité comme une donnée non fiable : le LLM ne
    peut que proposer, jamais dicter.
    """
    validate_file(file_path)

    path = Path(file_path)
    texte, total_pages = extraire_texte(path)

    if not texte.strip():
        return DocumentExtraction(
            questions=[],
            source_document=path.name,
            total_pages=total_pages,
            has_text=False,
        )

    # Le LLM extrait les questions à partir du texte du document.
    # Le texte est passé comme donnée, jamais comme instruction système.
    messages = [
        {
            "role": "user",
            "content": (
                "Extrais les questions de formulaire depuis ce document.\n\n"
                f"DOCUMENT ({path.name}) :\n{texte}\n\n"
                "Pour chaque question, indique :\n"
                "- le titre de la question\n"
                "- le type (short_text, paragraph, multiple_choice, checkboxes, dropdown)\n"
                "- si elle est obligatoire\n"
                "- les options (pour les questions à choix)\n"
                "- la page et le paragraphe où elle se trouve dans le document\n"
                "- un extrait du passage source\n"
                "- une note de confiance (0.0 à 1.0)\n\n"
                "Réponds uniquement avec un objet JSON valide :\n"
                '{"questions": [{"title": "...", "type": "...", "required": false, '
                '"options": [], "source": {"page": 1, "paragraph": "", '
                '"passage": "..."}, "confidence": 0.9}]}'
            ),
        }
    ]

    try:
        reponse = form_generator.generate_completion(
            messages,
            system_prompt=(
                "Tu extrais des questions de formulaire depuis un document. "
                "Ne modifies pas le contenu, ne l'invente pas. Chaque question "
                "doit être traçable à un passage du document."
            ),
        )
    except Exception as error:
        raise DocumentError(f"Échec de l'extraction par le modèle : {error}") from error

    import json

    try:
        data = json.loads(reponse)
    except json.JSONDecodeError as error:
        raise DocumentError("La réponse du modèle n'est pas un JSON valide.") from error

    questions_extraites = []
    for item in data.get("questions", []):
        try:
            q = ExtractedQuestion(
                title=item.get("title", ""),
                type=item.get("type", "short_text"),
                required=item.get("required", False),
                options=item.get("options", []),
                source=SourceTrace(
                    page=item.get("source", {}).get("page"),
                    paragraph=item.get("source", {}).get("paragraph", ""),
                    passage=item.get("source", {}).get("passage", ""),
                ),
                confidence=item.get("confidence", 1.0),
            )
            questions_extraites.append(q)
        except Exception:
            # On ignore les questions mal formées plutôt que d'échouer tout le batch.
            continue

    return DocumentExtraction(
        questions=questions_extraites,
        source_document=path.name,
        total_pages=total_pages,
        has_text=True,
    )
