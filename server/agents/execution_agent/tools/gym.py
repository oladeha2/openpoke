"""Gym lift tracking tool schemas and actions for the execution agent."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from server.services.gym import get_gym_store

_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "logLifts",
            "description": "Record sets for a gym exercise. Each set includes a set number, reps, and weight. Date defaults to today if not provided. Unit defaults to lbs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exercise": {
                        "type": "string",
                        "description": "Name of the exercise (e.g. 'deadlift', 'bench press', 'squat').",
                    },
                    "split": {
                        "type": "string",
                        "enum": ["push", "pull", "legs"],
                        "description": "The workout split this exercise belongs to.",
                    },
                    "sets": {
                        "type": "array",
                        "description": "Array of sets performed.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "set_number": {
                                    "type": "integer",
                                    "description": "Set number (1, 2, 3, etc.).",
                                },
                                "reps": {
                                    "type": "integer",
                                    "description": "Number of reps performed in this set.",
                                },
                                "weight": {
                                    "type": "number",
                                    "description": "Weight lifted in this set.",
                                },
                            },
                            "required": ["set_number", "reps", "weight"],
                        },
                    },
                    "date": {
                        "type": "string",
                        "description": "ISO date (YYYY-MM-DD) for the session. Defaults to today if omitted.",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["lbs", "kg"],
                        "description": "Weight unit. Defaults to 'lbs'.",
                    },
                },
                "required": ["exercise", "split", "sets"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "searchLifts",
            "description": "Search workout history with optional filters. Returns matching entries and summary stats (total sets, total volume, max weight, average weight). All filters are optional and can be combined.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exercise": {
                        "type": "string",
                        "description": "Filter by exercise name.",
                    },
                    "split": {
                        "type": "string",
                        "enum": ["push", "pull", "legs"],
                        "description": "Filter by workout split.",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Start of date range (inclusive, YYYY-MM-DD).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "End of date range (inclusive, YYYY-MM-DD).",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "updateLifts",
            "description": "Update matching lift entries by filter. Provide filters to select entries and the new values to apply. At least one of new_weight or new_reps must be provided.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exercise": {
                        "type": "string",
                        "description": "Filter by exercise name.",
                    },
                    "split": {
                        "type": "string",
                        "enum": ["push", "pull", "legs"],
                        "description": "Filter by workout split.",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Start of date range (inclusive, YYYY-MM-DD).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "End of date range (inclusive, YYYY-MM-DD).",
                    },
                    "new_weight": {
                        "type": "number",
                        "description": "New weight value to set on matching entries.",
                    },
                    "new_reps": {
                        "type": "integer",
                        "description": "New reps value to set on matching entries.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deleteLifts",
            "description": "Delete matching lift entries by filter. At least one filter is required to prevent accidental deletion of all data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exercise": {
                        "type": "string",
                        "description": "Filter by exercise name.",
                    },
                    "split": {
                        "type": "string",
                        "enum": ["push", "pull", "legs"],
                        "description": "Filter by workout split.",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Start of date range (inclusive, YYYY-MM-DD).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "End of date range (inclusive, YYYY-MM-DD).",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]


def get_schemas() -> List[Dict[str, Any]]:
    """Return gym lift tool schemas."""
    return _SCHEMAS


def _log_lifts_tool(
    *,
    exercise: str,
    split: str,
    sets: List[Dict[str, Any]],
    date: Optional[str] = None,
    unit: str = "lbs",
) -> Dict[str, Any]:
    store = get_gym_store()
    return store.log_lifts(exercise=exercise, sets=sets, split=split, lift_date=date, unit=unit)


def _search_lifts_tool(
    *,
    exercise: Optional[str] = None,
    split: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    store = get_gym_store()
    return store.search(exercise=exercise, split=split, date_from=date_from, date_to=date_to)


def _update_lifts_tool(
    *,
    exercise: Optional[str] = None,
    split: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    new_weight: Optional[float] = None,
    new_reps: Optional[int] = None,
) -> Dict[str, Any]:
    store = get_gym_store()
    return store.update(
        exercise=exercise,
        split=split,
        date_from=date_from,
        date_to=date_to,
        new_weight=new_weight,
        new_reps=new_reps,
    )


def _delete_lifts_tool(
    *,
    exercise: Optional[str] = None,
    split: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    store = get_gym_store()
    return store.delete(exercise=exercise, split=split, date_from=date_from, date_to=date_to)


def build_registry(agent_name: str) -> Dict[str, Callable[..., Any]]:
    """Return gym lift tool callables (agent_name accepted for signature consistency)."""
    return {
        "logLifts": _log_lifts_tool,
        "searchLifts": _search_lifts_tool,
        "updateLifts": _update_lifts_tool,
        "deleteLifts": _delete_lifts_tool,
    }


__all__ = [
    "build_registry",
    "get_schemas",
]
