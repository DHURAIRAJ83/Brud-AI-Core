"""Security extension points for later authentication and authorization.

Phase 1 intentionally has no authentication. Keeping policy hooks isolated here
allows a later phase to add them without coupling route handlers to a provider.
"""


def authentication_enabled() -> bool:
    """Report the Phase 1 authentication state."""

    return False
