"""User preference store with JSON persistence and semantic deduplication."""

import fcntl
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...config import get_settings
from ...logging_config import logger
from ...openrouter_client import request_embedding
from ...utils.similarity import cosine_similarity


class PreferenceStore:
    """Persistent store for user preferences backed by a JSON file."""

    def __init__(self, store_path: Path):
        self._path = store_path
        self._preferences: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Read preferences from disk."""
        if self._path.exists():
            try:
                with open(self._path, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._preferences = data
            except Exception as exc:
                logger.warning(f"Failed to load preferences: {exc}")
                self._preferences = []
        else:
            self._preferences = []
            self._save()

    def _save(self) -> None:
        """Write preferences to disk with file locking."""
        max_retries = 5
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)

                with open(self._path, "w") as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    try:
                        json.dump(self._preferences, f, indent=2)
                        return
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            except BlockingIOError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.warning("Failed to acquire lock on preferences file after retries")
            except Exception as exc:
                logger.warning(f"Failed to save preferences: {exc}")
                break

    def _next_id(self) -> int:
        """Return the next available preference ID."""
        if not self._preferences:
            return 1
        return max(p["id"] for p in self._preferences) + 1

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def add(self, content: str, source: str) -> Dict[str, Any]:
        """Add a new preference, merging into an existing one if semantically similar."""
        settings = get_settings()
        if len(self._preferences) >= settings.max_preferences:
            return {"error": "Preference limit reached. Remove existing preferences before adding new ones."}

        if source not in ("user", "agent"):
            return {"error": f"Invalid source: {source}. Must be 'user' or 'agent'."}

        embedding = await request_embedding(
            model=settings.embedding_model,
            input_text=content,
        )

        best_match: Optional[Dict[str, Any]] = None
        best_score: float = 0.0

        for pref in self._preferences:
            stored_embedding = pref.get("embedding")
            if not stored_embedding:
                continue
            score = cosine_similarity(embedding, stored_embedding)
            if score >= settings.preference_similarity_threshold and score > best_score:
                best_match = pref
                best_score = score

        now = self._now_iso()

        if best_match is not None:
            logger.info(
                f"Merging preference into existing id={best_match['id']} "
                f"(similarity={best_score:.3f})"
            )
            best_match["content"] = content
            best_match["embedding"] = embedding
            best_match["updated_at"] = now
            self._save()
            return self._without_embedding(best_match)

        preference = {
            "id": self._next_id(),
            "content": content,
            "source": source,
            "embedding": embedding,
            "created_at": now,
            "updated_at": now,
        }
        self._preferences.append(preference)
        self._save()
        return self._without_embedding(preference)

    @staticmethod
    def _without_embedding(pref: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of a preference dict without the embedding vector."""
        return {k: v for k, v in pref.items() if k != "embedding"}

    def update(self, preference_id: int, content: str) -> Optional[Dict[str, Any]]:
        """Update a preference's content by ID. Returns None if not found."""
        for pref in self._preferences:
            if pref["id"] == preference_id:
                pref["content"] = content
                pref["updated_at"] = self._now_iso()
                self._save()
                return pref
        return None

    def remove(self, preference_id: int) -> bool:
        """Remove a preference by ID. Returns True if found and removed."""
        original_len = len(self._preferences)
        self._preferences = [p for p in self._preferences if p["id"] != preference_id]
        if len(self._preferences) < original_len:
            self._save()
            return True
        return False

    def list_all(self) -> List[Dict[str, Any]]:
        """Return all preferences without embedding vectors."""
        return [self._without_embedding(p) for p in self._preferences]

    def clear(self) -> None:
        """Delete all preferences."""
        self._preferences = []
        try:
            if self._path.exists():
                self._path.unlink()
            logger.info("Cleared user preferences")
        except Exception as exc:
            logger.warning(f"Failed to clear preferences file: {exc}")


_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_PREFERENCES_PATH = _DATA_DIR / "preferences" / "user_preferences.json"

_store: Optional[PreferenceStore] = None


def get_preference_store() -> PreferenceStore:
    """Get the singleton preference store instance."""
    global _store
    if _store is None:
        _store = PreferenceStore(_PREFERENCES_PATH)
    return _store
