"""Client Google Forms : traduit un Form en requêtes Google, puis crée le formulaire.

Liens avec les autres fichiers
------------------------------
- schemas/form.py : fournit le Form à traduire (et CHOICE_TYPES).
- oauth.py        : obtient le jeton d'accès Google (fichier suivant).
- routes.py       : appellera create_form() après la confirmation de l'utilisateur.

Deux métiers séparés :
- form_to_requests() : fonction PURE (pas de réseau), facile à tester ;
- create_form()      : les deux appels HTTP vers Google.
"""

import httpx

from app.schemas.form import CHOICE_TYPES, Form, Question, QuestionType

FORMS_API_URL = "https://forms.googleapis.com/v1/forms"
REQUEST_TIMEOUT_SECONDS = 30.0

# Notre type de question à choix -> le type Google correspondant.
CHOICE_TYPE_TO_GOOGLE = {
    QuestionType.MULTIPLE_CHOICE: "RADIO",
    QuestionType.CHECKBOXES: "CHECKBOX",
    QuestionType.DROPDOWN: "DROP_DOWN",
}


def question_to_item(question: Question) -> dict:
    """Traduit une Question de Formia en « élément » Google Forms."""
    if question.type in CHOICE_TYPES:
        kind = {
            "choiceQuestion": {
                "type": CHOICE_TYPE_TO_GOOGLE[question.type],
                "options": [{"value": option} for option in question.options],
            }
        }
    else:
        # short_text -> paragraph False ; paragraph -> paragraph True.
        kind = {"textQuestion": {"paragraph": question.type == QuestionType.PARAGRAPH}}

    return {
        "title": question.title,
        "questionItem": {"question": {"required": question.required, **kind}},
    }


def form_to_requests(form: Form) -> list[dict]:
    """Construit la liste de sous-requêtes du batchUpdate pour un formulaire."""
    requests: list[dict] = []

    # La description ne peut pas être donnée à la création : on l'ajoute ici.
    if form.description:
        requests.append(
            {
                "updateFormInfo": {
                    "info": {"description": form.description},
                    "updateMask": "description",
                }
            }
        )

    # Google valide les sous-requêtes dans l'ordre : les index doivent être 0, 1, 2...
    for index, question in enumerate(form.questions):
        requests.append(
            {
                "createItem": {
                    "item": question_to_item(question),
                    "location": {"index": index},
                }
            }
        )
    return requests


def create_form(
    form: Form,
    access_token: str,
    *,
    confirmed_form: Form | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, str]:
    """Crée le formulaire dans le compte Google de l'utilisateur.

    confirmed_form : la version que l'utilisateur a confirmée. Elle doit être
    identique au formulaire à créer, sinon on refuse (règle de sécurité).
    transport : sert uniquement aux tests, pour simuler le réseau.
    """
    if not access_token:
        raise ValueError("Un jeton Google est requis côté backend.")
    if confirmed_form != form:
        raise PermissionError(
            "La confirmation doit porter sur la version exacte du formulaire."
        )

    # Le jeton ne sert qu'à cet en-tête : on ne l'affiche ni ne l'enregistre jamais.
    headers = {"Authorization": f"Bearer {access_token}"}

    with httpx.Client(
        timeout=REQUEST_TIMEOUT_SECONDS,
        transport=transport,
        headers=headers,
    ) as client:
        # Appel 1 : un formulaire vide (Google ne copie ici que les titres).
        created = client.post(
            FORMS_API_URL,
            json={"info": {"title": form.title, "documentTitle": form.title}},
        )
        created.raise_for_status()
        created_data = created.json()
        form_id = created_data["formId"]

        # Appel 2 : on ajoute la description et les questions.
        updated = client.post(
            f"{FORMS_API_URL}/{form_id}:batchUpdate",
            json={"requests": form_to_requests(form)},
        )
        updated.raise_for_status()

    return {
        "form_id": form_id,
        "responder_url": created_data.get("responderUri", ""),
        "edit_url": f"https://docs.google.com/forms/d/{form_id}/edit",
    }