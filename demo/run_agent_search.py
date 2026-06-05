"""Demo: Semantic search over execution agents.

Embeds a query and ranks pre-seeded agents by cosine similarity,
demonstrating the agent overload fix in action.

Usage:
    python demo/run_agent_search.py "check my latest emails from Alice"
    python demo/run_agent_search.py "what did I bench press last week" --top-k 3
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.openrouter_client import request_embedding
from server.config import get_settings
from server.utils.similarity import cosine_similarity

DATA_DIR = Path(__file__).resolve().parent / "demo_data"


def load_demo_data():
    embeddings_path = DATA_DIR / "agents_embeddings.json"
    roster_path = DATA_DIR / "agents_roster.json"

    if not embeddings_path.exists() or not roster_path.exists():
        print("Error: Demo data not found. Run 'python demo/seed_data.py' first.")
        sys.exit(1)

    with open(embeddings_path) as f:
        embeddings = json.load(f)
    with open(roster_path) as f:
        roster = json.load(f)

    return embeddings, roster


async def search(query: str, top_k: int):
    settings = get_settings()
    embeddings, roster = load_demo_data()
    roster_names = {entry["name"] for entry in roster}

    print(f"\nQuery: \"{query}\"")
    print(f"Top-K: {top_k}")
    print(f"Roster size: {len(roster_names)} agents")
    print("-" * 60)

    query_embedding = await request_embedding(
        model=settings.embedding_model,
        input_text=query,
    )

    scores = []
    for name, entry in embeddings.items():
        if name not in roster_names:
            continue
        stored_embedding = entry.get("embedding")
        if not stored_embedding:
            continue
        score = cosine_similarity(query_embedding, stored_embedding)
        scores.append((name, score, entry.get("instructions", [])))

    scores.sort(key=lambda x: x[1], reverse=True)

    print(f"\n{'Rank':<6}{'Agent':<30}{'Score':<10}{'Status'}")
    print("=" * 60)

    for i, (name, score, instructions) in enumerate(scores, 1):
        marker = "  SELECTED" if i <= top_k else ""
        print(f"{i:<6}{name:<30}{score:.4f}    {marker}")

    print("\n" + "=" * 60)
    print(f"\nAgents that would be rendered in context (top {top_k}):")
    for name, score, instructions in scores[:top_k]:
        instr_preview = instructions[0][:60] + "..." if instructions else "N/A"
        print(f"  - {name} (score: {score:.4f})")
        print(f"    Latest instruction: {instr_preview}")


def main():
    parser = argparse.ArgumentParser(
        description="Demo: Semantic search over execution agent embeddings"
    )
    parser.add_argument(
        "query",
        help="The search query to match against agent embeddings",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of top results to select (default: 5)",
    )

    args = parser.parse_args()
    asyncio.run(search(args.query, args.top_k))


if __name__ == "__main__":
    main()
