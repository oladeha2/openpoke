"""One-time script to generate embeddings for demo data.

Run from the project root:
    python demo/seed_data.py

Requires OPENROUTER_API_KEY in your .env file.
Outputs pre-seeded JSON files into demo/data/ that are committed to the repo.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.openrouter_client import request_embedding
from server.config import get_settings

DATA_DIR = Path(__file__).resolve().parent / "data"

AGENTS = [
    {
        "name": "Email to Alice",
        "instructions": [
            "Email Alice to ask if she's free for lunch tomorrow. Bob is also coming.",
            "Check if Alice replied to the lunch invitation we sent yesterday.",
        ],
    },
    {
        "name": "Email to Bob",
        "instructions": [
            "Send Bob the Q3 project status update and ask for his feedback by Friday.",
        ],
    },
    {
        "name": "Q3 Budget Analysis",
        "instructions": [
            "Search my emails for any budget-related messages from finance team in the last month and summarize spending.",
        ],
    },
    {
        "name": "Tokyo Restaurant Search",
        "instructions": [
            "Find the reservation confirmation for that sushi restaurant I went to in Tokyo last March.",
        ],
    },
    {
        "name": "Weekly Team Standup",
        "instructions": [
            "Set up a recurring reminder every Monday at 9am to prepare standup notes.",
            "Update the standup reminder to include a prompt to check Jira tickets.",
        ],
    },
    {
        "name": "Gym Progress Tracker",
        "instructions": [
            "Log today's workout: 4 sets of 8 bench press at 185 lbs, push day.",
        ],
    },
    {
        "name": "LinkedIn Job Applications",
        "instructions": [
            "Search my inbox for any responses from companies I applied to on LinkedIn this week.",
        ],
    },
    {
        "name": "Dentist Appointment",
        "instructions": [
            "Find Dr. Chen's email and schedule a cleaning for next Thursday afternoon.",
        ],
    },
    {
        "name": "Mom Birthday Gift",
        "instructions": [
            "Search my old emails with Mom to figure out what she mentioned wanting for her birthday.",
        ],
    },
    {
        "name": "Vercel Deployment Monitor",
        "instructions": [
            "Check for any deployment failure notifications from Vercel in the last 24 hours.",
        ],
    },
]

PREFERENCES = [
    {"content": "I like formal, professional tone in all emails", "source": "user"},
    {"content": "Always CC sarah@company.com on client emails", "source": "user"},
    {"content": "Prefer concise bullet-point summaries over long paragraphs", "source": "agent"},
    {"content": "Use metric units (kg) for gym tracking", "source": "user"},
    {"content": "Schedule meetings in the afternoon, never before 11am", "source": "agent"},
    {"content": "Reply to emails within the same day when possible", "source": "user"},
]


async def seed_agents():
    """Generate embeddings for demo agents and write to JSON files."""
    settings = get_settings()
    embeddings_data = {}
    roster_data = []

    for i, agent in enumerate(AGENTS):
        name = agent["name"]
        instructions = agent["instructions"]
        embedding_text = f"{name}: {' | '.join(instructions)}"

        print(f"  Embedding agent {i+1}/{len(AGENTS)}: {name}")
        embedding = await request_embedding(
            model=settings.embedding_model,
            input_text=embedding_text,
        )

        embeddings_data[name] = {
            "embedding": embedding,
            "instructions": instructions,
            "last_updated": "2026-06-04T12:00:00+00:00",
        }

        roster_data.append({
            "name": name,
            "last_interacted": f"2026-06-0{min(i+1, 5)}T{10+i}:00:00+00:00",
        })

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATA_DIR / "agents_embeddings.json", "w") as f:
        json.dump(embeddings_data, f, indent=2)

    with open(DATA_DIR / "agents_roster.json", "w") as f:
        json.dump(roster_data, f, indent=2)

    print(f"  Wrote {len(AGENTS)} agents to demo/data/")


async def seed_preferences():
    """Generate embeddings for demo preferences and write to JSON."""
    settings = get_settings()
    preferences_data = []

    for i, pref in enumerate(PREFERENCES):
        print(f"  Embedding preference {i+1}/{len(PREFERENCES)}: {pref['content'][:50]}...")
        embedding = await request_embedding(
            model=settings.embedding_model,
            input_text=pref["content"],
        )

        preferences_data.append({
            "id": i + 1,
            "content": pref["content"],
            "source": pref["source"],
            "embedding": embedding,
            "created_at": "2026-06-04T12:00:00+00:00",
            "updated_at": "2026-06-04T12:00:00+00:00",
        })

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATA_DIR / "preferences.json", "w") as f:
        json.dump(preferences_data, f, indent=2)

    print(f"  Wrote {len(PREFERENCES)} preferences to demo/data/")


async def main():
    print("Seeding demo data...\n")

    print("[1/2] Generating agent embeddings...")
    await seed_agents()

    print("\n[2/2] Generating preference embeddings...")
    await seed_preferences()

    print("\nDone! Demo data files are ready in demo/data/")


if __name__ == "__main__":
    asyncio.run(main())
