"""JSON-backed store for agent embeddings with cosine similarity search."""

import json
import fcntl
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...config import get_settings
from ...logging_config import logger
from ...openrouter_client import request_embedding
from ...utils.similarity import cosine_similarity


class AgentEmbeddingStore:
    """Manages agent embeddings for semantic search."""

    def __init__(self, store_path: Path):
        self._path = store_path
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._data = data
            except Exception as exc:
                logger.warning(f"Failed to load embeddings.json: {exc}")
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        max_retries = 5
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)

                with open(self._path, 'w') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    try:
                        json.dump(self._data, f, indent=2)
                        return
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            except BlockingIOError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.warning("Failed to acquire lock on embeddings.json after retries")
            except Exception as exc:
                logger.warning(f"Failed to save embeddings.json: {exc}")
                break

    async def upsert(self, agent_name: str, instructions: str) -> None:
        """Update or create an embedding for an agent."""
        settings = get_settings()
        max_instructions = settings.max_agent_instructions_for_embedding

        entry = self._data.get(agent_name, {})
        instructions_list: List[str] = entry.get("instructions", [])
        instructions_list.append(instructions)
        instructions_list = instructions_list[-max_instructions:]

        embedding_text = f"{agent_name}: {' | '.join(instructions_list)}"
        embedding = await request_embedding(
            model=settings.embedding_model,
            input_text=embedding_text,
        )

        self._data[agent_name] = {
            "embedding": embedding,
            "instructions": instructions_list,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

    async def search(
        self,
        query_text: str,
        top_k: int,
        candidate_names: Optional[List[str]] = None,
    ) -> List[str]:
        """Find the most relevant agents by cosine similarity."""
        settings = get_settings()
        query_embedding = await request_embedding(
            model=settings.embedding_model,
            input_text=query_text,
        )

        scores: List[tuple[str, float]] = []
        for name, entry in self._data.items():
            if candidate_names is not None and name not in candidate_names:
                continue
            stored_embedding = entry.get("embedding")
            if not stored_embedding:
                continue
            similarity = cosine_similarity(query_embedding, stored_embedding)
            scores.append((name, similarity))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [name for name, _ in scores[:top_k]]

    def remove(self, agent_name: str) -> None:
        """Delete an agent's embedding."""
        if agent_name in self._data:
            del self._data[agent_name]
            self._save()

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_EMBEDDINGS_PATH = _DATA_DIR / "execution_agents" / "embeddings.json"

_store: Optional[AgentEmbeddingStore] = None


def get_embedding_store() -> AgentEmbeddingStore:
    """Get the singleton embedding store instance."""
    global _store
    if _store is None:
        _store = AgentEmbeddingStore(_EMBEDDINGS_PATH)
    return _store
