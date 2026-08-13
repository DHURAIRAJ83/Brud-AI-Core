"""MB-24: Permission Scope Registry -- pure. The fixed registry of
every permission scope a plugin may ever request -- the task spec's
own Step 4 list, verbatim, each with a sensitivity level, a default
policy decision, a consent requirement, an admin-review requirement,
and a public-chat availability flag. No scope outside this fixed
registry is ever recognized -- `plugin_manifest_validator.py` rejects
any manifest that requests an unknown scope.
"""

from __future__ import annotations

from typing import Any

SENSITIVITY_LEVELS = ("low", "medium", "high", "critical")
DECISIONS = ("allow", "deny", "require_consent", "require_admin_review", "disabled")

SCOPE_REGISTRY: dict[str, dict[str, Any]] = {
    "chat.read.current": {
        "sensitivity": "low", "default_policy": "allow", "consent_required": False,
        "admin_review_required": False, "public_chat_available": True,
        "description": "Read the current in-flight chat turn only -- never conversation history.",
    },
    "chat.read.history": {
        "sensitivity": "high", "default_policy": "require_consent", "consent_required": True,
        "admin_review_required": False, "public_chat_available": True,
        "description": "Read prior chat history for this session -- requires explicit user consent.",
    },
    "filesystem.read.user_selected": {
        "sensitivity": "medium", "default_policy": "require_consent", "consent_required": True,
        "admin_review_required": False, "public_chat_available": True,
        "description": "Read files from a path the user explicitly selected, never an arbitrary path.",
    },
    "filesystem.write.user_selected": {
        "sensitivity": "high", "default_policy": "require_admin_review", "consent_required": True,
        "admin_review_required": True, "public_chat_available": False,
        "description": "Write files to a path the user explicitly selected.",
    },
    "network.http.allowed_domains": {
        "sensitivity": "medium", "default_policy": "require_consent", "consent_required": True,
        "admin_review_required": False, "public_chat_available": True,
        "description": "Make HTTP requests, bounded to the plugin's own declared allowed_domains list.",
    },
    "image.generate.local": {
        "sensitivity": "low", "default_policy": "allow", "consent_required": False,
        "admin_review_required": False, "public_chat_available": True,
        "description": "Generate an image using a local, already-approved model.",
    },
    "image.generate.external": {
        "sensitivity": "medium", "default_policy": "require_consent", "consent_required": True,
        "admin_review_required": False, "public_chat_available": True,
        "description": "Generate an image via an external network call.",
    },
    "calendar.read": {
        "sensitivity": "medium", "default_policy": "require_consent", "consent_required": True,
        "admin_review_required": False, "public_chat_available": True,
        "description": "Read the user's calendar.",
    },
    "calendar.write": {
        "sensitivity": "high", "default_policy": "require_admin_review", "consent_required": True,
        "admin_review_required": True, "public_chat_available": False,
        "description": "Create or modify calendar events on the user's behalf.",
    },
    "email.send": {
        "sensitivity": "critical", "default_policy": "require_admin_review", "consent_required": True,
        "admin_review_required": True, "public_chat_available": False,
        "description": "Send an email on the user's behalf.",
    },
    "clipboard.read": {
        "sensitivity": "medium", "default_policy": "require_consent", "consent_required": True,
        "admin_review_required": False, "public_chat_available": True,
        "description": "Read the system clipboard.",
    },
    "clipboard.write": {
        "sensitivity": "medium", "default_policy": "require_consent", "consent_required": True,
        "admin_review_required": False, "public_chat_available": True,
        "description": "Write to the system clipboard.",
    },
    "microphone.capture": {
        "sensitivity": "high", "default_policy": "require_admin_review", "consent_required": True,
        "admin_review_required": True, "public_chat_available": False,
        "description": "Capture audio from the microphone.",
    },
    "camera.capture": {
        "sensitivity": "high", "default_policy": "require_admin_review", "consent_required": True,
        "admin_review_required": True, "public_chat_available": False,
        "description": "Capture an image or video from the camera.",
    },
    "plugin.storage.local": {
        "sensitivity": "low", "default_policy": "allow", "consent_required": False,
        "admin_review_required": False, "public_chat_available": True,
        "description": "Use the plugin's own local, sandboxed storage bucket.",
    },
    "plugin.storage.cloud": {
        "sensitivity": "medium", "default_policy": "require_consent", "consent_required": True,
        "admin_review_required": False, "public_chat_available": True,
        "description": "Use the plugin's own cloud storage bucket.",
    },
    "admin.assistant.invoke": {
        "sensitivity": "critical", "default_policy": "require_admin_review", "consent_required": False,
        "admin_review_required": True, "public_chat_available": False,
        "description": "Invoke the Admin Assistant on the user's behalf -- admin-review only, never a user-consent scope.",
    },
}


def known_scopes() -> tuple[str, ...]:
    return tuple(SCOPE_REGISTRY)


def scope_definition(scope_key: str) -> dict[str, Any] | None:
    return SCOPE_REGISTRY.get(scope_key)


def is_known_scope(scope_key: str) -> bool:
    return scope_key in SCOPE_REGISTRY


def is_public_chat_available(scope_key: str) -> bool:
    definition = SCOPE_REGISTRY.get(scope_key)
    return bool(definition and definition["public_chat_available"])
