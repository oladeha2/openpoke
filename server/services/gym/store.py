"""Gym lift store with JSON persistence and filter-based operations."""

import fcntl
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...logging_config import logger

VALID_SPLITS = {"push", "pull", "legs"}
VALID_UNITS = {"lbs", "kg"}


class GymLiftStore:
    """Persistent store for gym lift entries backed by a JSON file."""

    def __init__(self, store_path: Path):
        self._path = store_path
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._entries = data
            except Exception as exc:
                logger.warning(f"Failed to load gym lifts: {exc}")
                self._entries = []
        else:
            self._entries = []
            self._save()

    def _save(self) -> None:
        max_retries = 5
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)

                with open(self._path, "w") as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    try:
                        json.dump(self._entries, f, indent=2)
                        return
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            except BlockingIOError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.warning("Failed to acquire lock on gym lifts file after retries")
            except Exception as exc:
                logger.warning(f"Failed to save gym lifts: {exc}")
                break

    def _next_id(self) -> int:
        if not self._entries:
            return 1
        return max(e["id"] for e in self._entries) + 1

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _today_iso(self) -> str:
        return date.today().isoformat()

    def _filter(
        self,
        entries: List[Dict[str, Any]],
        exercise: Optional[str] = None,
        split: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        result = entries
        if exercise:
            exercise_lower = exercise.lower()
            result = [e for e in result if e["exercise"].lower() == exercise_lower]
        if split:
            result = [e for e in result if e["split"] == split.lower()]
        if date_from:
            result = [e for e in result if e["date"] >= date_from]
        if date_to:
            result = [e for e in result if e["date"] <= date_to]
        return result

    def _compute_stats(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not entries:
            return {"total_sets": 0, "total_volume": 0, "max_weight": 0, "avg_weight": 0}

        total_sets = len(entries)
        total_volume = sum(e["reps"] * e["weight"] for e in entries)
        max_weight = max(e["weight"] for e in entries)
        avg_weight = round(sum(e["weight"] for e in entries) / total_sets, 1)

        return {
            "total_sets": total_sets,
            "total_volume": total_volume,
            "max_weight": max_weight,
            "avg_weight": avg_weight,
        }

    def log_lifts(
        self,
        exercise: str,
        sets: List[Dict[str, Any]],
        split: str,
        lift_date: Optional[str] = None,
        unit: str = "lbs",
    ) -> Dict[str, Any]:
        split_lower = split.lower()
        if split_lower not in VALID_SPLITS:
            return {"error": f"Invalid split: {split}. Must be one of: {', '.join(sorted(VALID_SPLITS))}"}

        unit_lower = unit.lower()
        if unit_lower not in VALID_UNITS:
            return {"error": f"Invalid unit: {unit}. Must be one of: {', '.join(sorted(VALID_UNITS))}"}

        resolved_date = lift_date or self._today_iso()
        now = self._now_iso()
        created: List[Dict[str, Any]] = []

        for s in sets:
            entry = {
                "id": self._next_id(),
                "exercise": exercise.lower(),
                "set_number": s["set_number"],
                "reps": s["reps"],
                "weight": s["weight"],
                "unit": unit_lower,
                "split": split_lower,
                "date": resolved_date,
                "created_at": now,
                "updated_at": now,
            }
            self._entries.append(entry)
            created.append(entry)

        self._save()
        return {"entries": created, "count": len(created)}

    def search(
        self,
        exercise: Optional[str] = None,
        split: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        matched = self._filter(self._entries, exercise, split, date_from, date_to)
        return {"entries": matched, "stats": self._compute_stats(matched)}

    def update(
        self,
        exercise: Optional[str] = None,
        split: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        new_weight: Optional[float] = None,
        new_reps: Optional[int] = None,
    ) -> Dict[str, Any]:
        if new_weight is None and new_reps is None:
            return {"error": "At least one of new_weight or new_reps must be provided."}

        matched = self._filter(self._entries, exercise, split, date_from, date_to)
        now = self._now_iso()

        for entry in matched:
            if new_weight is not None:
                entry["weight"] = new_weight
            if new_reps is not None:
                entry["reps"] = new_reps
            entry["updated_at"] = now

        if matched:
            self._save()

        return {"updated_count": len(matched), "entries": matched}

    def delete(
        self,
        exercise: Optional[str] = None,
        split: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not any([exercise, split, date_from, date_to]):
            return {"error": "At least one filter is required to prevent accidental deletion of all entries."}

        matched_ids = {e["id"] for e in self._filter(self._entries, exercise, split, date_from, date_to)}
        original_len = len(self._entries)
        self._entries = [e for e in self._entries if e["id"] not in matched_ids]
        deleted_count = original_len - len(self._entries)

        if deleted_count > 0:
            self._save()

        return {"deleted_count": deleted_count}


_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_LIFTS_PATH = _DATA_DIR / "gym" / "lifts.json"

_store: Optional[GymLiftStore] = None


def get_gym_store() -> GymLiftStore:
    """Get the singleton gym lift store instance."""
    global _store
    if _store is None:
        _store = GymLiftStore(_LIFTS_PATH)
    return _store
