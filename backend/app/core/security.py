"""Primitives de sécurité OAuth."""

import secrets


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(32)


def verify_oauth_state(expected_state: str, received_state: str) -> bool:
    return bool(expected_state and received_state) and secrets.compare_digest(
        expected_state, received_state
    )
