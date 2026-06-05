"""Agent roster management with recency tracking."""

import json
import fcntl
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ...config import get_settings
from ...logging_config import logger


class AgentRoster:
    """Roster that stores agent names with last-interacted timestamps."""

    def __init__(self, roster_path: Path):
        self._roster_path = roster_path
        self._agents: List[Dict[str, str]] = []
        self.load()

    def load(self) -> None:
        """Load agents from roster.json."""
        if self._roster_path.exists():
            try:
                with open(self._roster_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._agents = [
                            entry for entry in data
                            if isinstance(entry, dict) and "name" in entry
                        ]
            except Exception as exc:
                logger.warning(f"Failed to load roster.json: {exc}")
                self._agents = []
        else:
            self._agents = []
            self.save()

    def save(self) -> None:
        """Save agents to roster.json with file locking."""
        max_retries = 5
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                self._roster_path.parent.mkdir(parents=True, exist_ok=True)

                with open(self._roster_path, 'w') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    try:
                        json.dump(self._agents, f, indent=2)
                        return
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            except BlockingIOError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.warning("Failed to acquire lock on roster.json after retries")
            except Exception as exc:
                logger.warning(f"Failed to save roster.json: {exc}")
                break

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _find_entry(self, agent_name: str) -> Optional[Dict[str, str]]:
        for entry in self._agents:
            if entry["name"] == agent_name:
                return entry
        return None

    def add_agent(self, agent_name: str) -> None:
        """Add an agent to the roster if not already present.

        Enforces the hard cap: when the roster exceeds max_execution_agents,
        the least recently interacted agent(s) are evicted along with their
        embeddings.
        """
        if self._find_entry(agent_name) is None:
            self._agents.append({
                "name": agent_name,
                "last_interacted": self._now_iso(),
            })

            cap = get_settings().max_execution_agents
            if len(self._agents) > cap:
                sorted_agents = sorted(
                    self._agents,
                    key=lambda e: e.get("last_interacted", ""),
                )
                evict_count = len(self._agents) - cap
                to_evict = sorted_agents[:evict_count]
                evicted_names = {e["name"] for e in to_evict}
                self._agents = [e for e in self._agents if e["name"] not in evicted_names]

                for name in evicted_names:
                    logger.info(f"Evicted agent from roster: {name}")
                    try:
                        from .embedding_store import get_embedding_store
                        get_embedding_store().remove(name)
                    except Exception:
                        pass

            self.save()

    def touch_agent(self, agent_name: str) -> None:
        """Update last_interacted timestamp for an existing agent."""
        entry = self._find_entry(agent_name)
        if entry is not None:
            entry["last_interacted"] = self._now_iso()
            self.save()

    def get_agents(self) -> List[str]:
        """Get list of all agent names."""
        return [entry["name"] for entry in self._agents]

    def get_agents_by_recency(self, top_k: int) -> List[str]:
        """Return top_k agent names sorted by most recent interaction first."""
        sorted_agents = sorted(
            self._agents,
            key=lambda e: e.get("last_interacted", ""),
            reverse=True,
        )
        return [entry["name"] for entry in sorted_agents[:top_k]]

    def remove_agent(self, agent_name: str) -> None:
        """Remove a specific agent from the roster by name."""
        self._agents = [e for e in self._agents if e["name"] != agent_name]
        self.save()

    def clear(self) -> None:
        """Clear the agent roster."""
        self._agents = []
        try:
            if self._roster_path.exists():
                self._roster_path.unlink()
            logger.info("Cleared agent roster")
        except Exception as exc:
            logger.warning(f"Failed to clear roster.json: {exc}")


_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_ROSTER_PATH = _DATA_DIR / "execution_agents" / "roster.json"

_agent_roster = AgentRoster(_ROSTER_PATH)


def get_agent_roster() -> AgentRoster:
    """Get the singleton roster instance."""
    return _agent_roster
