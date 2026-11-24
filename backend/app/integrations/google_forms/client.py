"""Client Google Forms : traduit un Form en requêtes Google, puis crée le formulaire.

Liens avec les autres fichiers
------------------------------
- schemas/form.py        : fournit le Form à traduire (et CHOICE_TYPES).
- oauth.py               : fournit le jeton d'accès Google.
- core/exceptions.py     : erreurs métier (GoogleError, PartialCreation).
- routes.py              : appelle create_form() après confirmation, en
                           mémorisant le `form_id` via `on_form_created`.

Deux métiers séparés :
- form_to_requests() : fonction PURE (pas de réseau), facile à tester ;
- create_form()      : les appels HTTP vers Google, avec reprise.

Création en deux temps, imposée par l'API : `forms.create` ne prend que le
titre, les questions s'ajoutent par `batchUpdate`. Si le second appel échoue,
`PartialCreation` transporte le `form_id` pour reprendre sur le MÊME formulaire.
La reprise relit d'abord le formulaire pour ne pas dupliquer les questions déjà
créées.
"""

import httpx

from app.core.exceptions import GoogleError
from app.schemas.form import CHOICE_TYPES, Form, Question, QuestionType

FORMS_API_URL = "https://forms.googleapis.com/v1/forms"
REQUEST_TIMEOUT_SECONDS = 30.0

# Notre type de question à choix -> le type Google correspondant.
CHOICE_TYPE_TO_GOOGLE = {
    QuestionType.MULTIPLE_CHOICE: "RADIO",
    QuestionType.CHECKBOXES: "CHECKBOX",
    QuestionType.DROPDOWN: "DROP_DOWN",
}


class PartialCreation(GoogleError):
    """Le formulaire existe chez Google, mais toutes ses questions n'ont pas
    pu être ajoutées. Le `form_id` permet de reprendre sans créer de doublon.
    """

    def __init__(self, form_id: str, edit_url: str) -> None:
        self.form_id = form_id
        self.edit_url = edit_url
        super().__init__(
            "Le formulaire a été créé, mais ses questions n'ont pas pu être "
            f"ajoutées. Formulaire : {edit_url} . Relancez la confirmation "
            "pour reprendre sur ce même formulaire."
        )


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


def form_to_requests(form: Form, *, first_question_index: int = 0) -> list[dict]:
    """Construit les sous-requêtes du batchUpdate.

    first_question_index : nombre de questions déjà présentes chez Google.
    Sert à la reprise : les index doivent correspondre à la position réelle.
    La mise à jour de description est idempotente et peut être renvoyée.
    """
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

    # Google valide les sous-requêtes dans l'ordre : les index doivent suivre.
    for offset, question in enumerate(form.questions[first_question_index:]):
        requests.append(
            {
                "createItem": {
                    "item": question_to_item(question),
                    "location": {"index": first_question_index + offset},
                }
            }
        )
    return requests


def _request(client: httpx.Client, method: str, url: str, **kwargs) -> dict:
    """Envoie un appel Google et traduit les pannes en erreur métier."""
    try:
        response = client.request(method, url, **kwargs)
    except httpx.HTTPError as error:
        raise GoogleError() from error

    if response.status_code >= 400:
        # On ne recopie jamais le corps de la réponse : il peut contenir des
        # détails internes du compte de l'utilisateur.
        raise GoogleError()
    try:
        data = response.json()
    except ValueError as error:
        raise GoogleError() from error
    if not isinstance(data, dict):
        raise GoogleError()
    return data


def create_form(
    form: Form,
    access_token: str,
    *,
    confirmed_form: Form | None = None,
    existing_form_id: str | None = None,
    on_form_created=None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, str]:
    """Crée le formulaire dans le compte Google de l'utilisateur.

    confirmed_form : la version que l'utilisateur a confirmée. Elle doit être
    identique au formulaire à créer, sinon on refuse (règle de sécurité).
    existing_form_id : reprise d'une création Google partielle.
    on_form_created : callback appelé dès réception du `form_id`, avant le
    second appel, pour que l'appelant puisse le mémoriser.
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
        if existing_form_id:
            form_id = existing_form_id
            remote = _request(client, "GET", f"{FORMS_API_URL}/{form_id}")
            # Reprise : on ne recrée que les questions absentes.
            existing_items = remote.get("items")
            existing_count = len(existing_items) if isinstance(existing_items, list) else 0
            responder_url = str(remote.get("responderUri") or "")
        else:
            # Appel 1 : un formulaire vide (Google ne copie ici que les titres).
            created_data = _request(
                client,
                "POST",
                FORMS_API_URL,
                json={"info": {"title": form.title, "documentTitle": form.title}},
            )
            form_id = created_data.get("formId")
            if not isinstance(form_id, str) or not form_id:
                raise GoogleError()
            responder_url = str(created_data.get("responderUri") or "")
            existing_count = 0
            if on_form_created is not None:
                on_form_created(form_id)

        edit_url = f"https://docs.google.com/forms/d/{form_id}/edit"

        # Appel 2 : description et questions restantes.
        requests = form_to_requests(form, first_question_index=existing_count)
        if requests:
            try:
                _request(
                    client,
                    "POST",
                    f"{FORMS_API_URL}/{form_id}:batchUpdate",
                    json={"requests": requests},
                )
            except GoogleError as error:
                raise PartialCreation(form_id, edit_url) from error

    return {
        "form_id": form_id,
        "responder_url": responder_url,
        "edit_url": edit_url,
    }
