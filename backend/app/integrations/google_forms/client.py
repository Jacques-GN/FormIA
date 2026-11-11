"""Client Google Forms à implémenter avant tout appel à l'API Google."""

from app.schemas.form import Form


async def create_form(
    form: Form,
    access_token: str,
    *,
    confirmed_form: Form | None = None,
) -> dict[str, object]:
    if not access_token:
        raise ValueError("Un jeton Google est requis côté backend.")
    if confirmed_form != form:
        raise PermissionError(
            "La confirmation doit porter sur la version exacte du formulaire."
        )

    raise NotImplementedError("Le client Google Forms n'est pas encore implémenté.")
