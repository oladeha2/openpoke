"""Demo: Preference deduplication via semantic similarity.

Embeds a new preference and checks it against pre-seeded preferences,
demonstrating the dedup logic that prevents near-duplicate preferences.

Usage:
    python demo/run_preference_dedup.py "I prefer a casual tone in my emails"
    python demo/run_preference_dedup.py "use kg not lbs for weights" --threshold 0.80
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


def load_demo_preferences():
    prefs_path = DATA_DIR / "preferences.json"

    if not prefs_path.exists():
        print("Error: Demo data not found. Run 'python demo/seed_data.py' first.")
        sys.exit(1)

    with open(prefs_path) as f:
        return json.load(f)


async def check_dedup(new_preference: str, threshold: float):
    settings = get_settings()
    preferences = load_demo_preferences()

    print(f"\nNew preference: \"{new_preference}\"")
    print(f"Threshold: {threshold}")
    print(f"Existing preferences: {len(preferences)}")
    print("-" * 70)

    new_embedding = await request_embedding(
        model=settings.embedding_model,
        input_text=new_preference,
    )

    scores = []
    for pref in preferences:
        stored_embedding = pref.get("embedding")
        if not stored_embedding:
            continue
        score = cosine_similarity(new_embedding, stored_embedding)
        scores.append((pref, score))

    scores.sort(key=lambda x: x[1], reverse=True)

    print(f"\n{'ID':<5}{'Score':<10}{'Status':<12}{'Preference'}")
    print("=" * 70)

    merge_target = None
    for pref, score in scores:
        if score >= threshold and merge_target is None:
            status = "MERGE"
            merge_target = pref
        elif score >= threshold:
            status = "ABOVE"
        else:
            status = "-"
        print(f"{pref['id']:<5}{score:.4f}    {status:<12}{pref['content']}")

    print("\n" + "=" * 70)

    if merge_target:
        print(f"\nResult: MERGE DETECTED")
        print(f"  The new preference would be merged into existing preference id={merge_target['id']}")
        print(f"  Existing: \"{merge_target['content']}\"")
        print(f"  New:      \"{new_preference}\"")
        print(f"  Score:    {scores[0][1]:.4f} (threshold: {threshold})")
        print(f"\n  In production, the existing preference's content would be replaced")
        print(f"  with the new text and its embedding re-generated.")
    else:
        print(f"\nResult: NO DUPLICATE DETECTED")
        print(f"  The new preference would be added as a new entry.")
        print(f"  Highest similarity: {scores[0][1]:.4f} (below threshold: {threshold})")


def main():
    parser = argparse.ArgumentParser(
        description="Demo: Preference deduplication via semantic similarity"
    )
    parser.add_argument(
        "preference",
        help="The new preference text to check for duplicates",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Similarity threshold for merge detection (default: 0.85)",
    )

    args = parser.parse_args()
    asyncio.run(check_dedup(args.preference, args.threshold))


if __name__ == "__main__":
    main()
