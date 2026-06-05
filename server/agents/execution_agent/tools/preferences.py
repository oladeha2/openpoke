"""Preference tool schemas and actions for the execution agent."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from server.services.preferences import get_preference_store

_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "addPreference",
            "description": "Save a new user preference. The preference should be a clear, specific natural language statement about the user's preferences or habits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The preference text to save.",
                    },
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "updatePreference",
            "description": "Update an existing user preference by ID. Use listPreferences first to find the correct ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "preference_id": {
                        "type": "integer",
                        "description": "The ID of the preference to update.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The updated preference text.",
                    },
                },
                "required": ["preference_id", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "removePreference",
            "description": "Remove a user preference by ID. Use listPreferences first to find the correct ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "preference_id": {
                        "type": "integer",
                        "description": "The ID of the preference to remove.",
                    },
                },
                "required": ["preference_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listPreferences",
            "description": "List all stored user preferences.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]


def get_schemas() -> List[Dict[str, Any]]:
    """Return preference tool schemas."""
    return _SCHEMAS


async def _add_preference_tool(*, content: str) -> Dict[str, Any]:
    store = get_preference_store()
    return await store.add(content, source="user")


def _update_preference_tool(*, preference_id: Any, content: str) -> Dict[str, Any]:
    try:
        pid = int(preference_id)
    except (TypeError, ValueError):
        return {"error": "preference_id must be an integer"}

    store = get_preference_store()
    result = store.update(pid, content)
    if result is None:
        return {"error": "Preference not found"}
    return result


def _remove_preference_tool(*, preference_id: Any) -> Dict[str, Any]:
    try:
        pid = int(preference_id)
    except (TypeError, ValueError):
        return {"error": "preference_id must be an integer"}

    store = get_preference_store()
    if store.remove(pid):
        return {"status": "removed"}
    return {"error": "Preference not found"}


def _list_preferences_tool() -> Dict[str, Any]:
    store = get_preference_store()
    return {"preferences": store.list_all()}


def build_registry(agent_name: str) -> Dict[str, Callable[..., Any]]:
    """Return preference tool callables (agent_name accepted for signature consistency)."""
    return {
        "addPreference": _add_preference_tool,
        "updatePreference": _update_preference_tool,
        "removePreference": _remove_preference_tool,
        "listPreferences": _list_preferences_tool,
    }


__all__ = [
    "build_registry",
    "get_schemas",
]
