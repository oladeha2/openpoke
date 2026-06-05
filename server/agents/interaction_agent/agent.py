"""Interaction agent helpers for prompt construction."""

from html import escape
from pathlib import Path
from typing import Dict, List

from ...config import get_settings
from ...logging_config import logger
from ...services.execution import get_agent_roster, get_embedding_store
from ...services.preferences import get_preference_store

_prompt_path = Path(__file__).parent / "system_prompt.md"
SYSTEM_PROMPT = _prompt_path.read_text(encoding="utf-8").strip()


def build_system_prompt() -> str:
    """Return the static system prompt for the interaction agent."""
    return SYSTEM_PROMPT


async def prepare_message_with_history(
    latest_text: str,
    transcript: str,
    message_type: str = "user",
) -> List[Dict[str, str]]:
    """Compose a message that bundles history, roster, and the latest turn."""
    sections: List[str] = []

    sections.append(f"<user_preferences>\n{_render_user_preferences()}\n</user_preferences>")
    sections.append(_render_conversation_history(transcript))
    agent_section = await _render_active_agents(latest_text)
    sections.append(f"<active_agents>\n{agent_section}\n</active_agents>")
    sections.append(_render_current_turn(latest_text, message_type))

    content = "\n\n".join(sections)
    return [{"role": "user", "content": content}]


def _render_user_preferences() -> str:
    """Render stored user preferences as XML for prompt injection."""
    store = get_preference_store()
    preferences = store.list_all()

    if not preferences:
        return "None"

    rendered: List[str] = []
    for pref in preferences:
        pref_id = pref["id"]
        source = escape(pref.get("source", "user"), quote=True)
        content = escape(pref.get("content", ""), quote=False)
        rendered.append(f'<preference id="{pref_id}" source="{source}">{content}</preference>')

    return "\n".join(rendered)


def _render_conversation_history(transcript: str) -> str:
    history = transcript.strip()
    if not history:
        history = "None"
    return f"<conversation_history>\n{history}\n</conversation_history>"


def _format_agent_list(agents: List[str]) -> str:
    rendered: List[str] = []
    for agent_name in agents:
        name = escape(agent_name or "agent", quote=True)
        rendered.append(f'<agent name="{name}" />')
    return "\n".join(rendered)


async def _render_active_agents(query_text: str) -> str:
    """Return filtered agent list using blended semantic + recency search."""
    roster = get_agent_roster()
    roster.load()
    all_agents = roster.get_agents()

    if not all_agents:
        return "None"

    settings = get_settings()
    top_k = settings.top_k_agents

    if len(all_agents) <= top_k:
        return _format_agent_list(all_agents)

    # Semantic search (best-effort)
    try:
        store = get_embedding_store()
        semantic_results = await store.search(
            query_text, top_k=top_k, candidate_names=all_agents
        )
        logger.info(f"Retrieved agents: {semantic_results} from semantic search")
    except Exception:
        logger.warning("Semantic search failed, using recency only")
        semantic_results = []

    # Recency-sorted agents
    recency_results = roster.get_agents_by_recency(top_k)

    # Blend: semantic first, fill remaining slots with recent agents
    merged = list(semantic_results)
    for agent in recency_results:
        if agent not in merged and len(merged) < top_k:
            merged.append(agent)

    return _format_agent_list(merged)


def _render_current_turn(latest_text: str, message_type: str) -> str:
    tag = "new_agent_message" if message_type == "agent" else "new_user_message"
    body = latest_text.strip()
    return f"<{tag}>\n{body}\n</{tag}>"
