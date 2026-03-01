"""Generate realistic sample data for local testing of the dashboard."""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DAILY_DIR = DATA_DIR / "daily"

REPOS = [
    ("vercel/next.js", "TypeScript", 132000),
    ("facebook/react", "JavaScript", 230000),
    ("microsoft/vscode", "TypeScript", 168000),
    ("langchain-ai/langchain", "Python", 98000),
    ("huggingface/transformers", "Python", 140000),
    ("fastapi/fastapi", "Python", 80000),
    ("sveltejs/svelte", "JavaScript", 82000),
    ("denoland/deno", "Rust", 98000),
    ("golang/go", "Go", 125000),
    ("rust-lang/rust", "Rust", 100000),
    ("django/django", "Python", 81000),
    ("pallets/flask", "Python", 69000),
    ("torvalds/linux", "C", 185000),
    ("kubernetes/kubernetes", "Go", 112000),
    ("apache/spark", "Scala", 40000),
    ("tailwindlabs/tailwindcss", "JavaScript", 84000),
    ("prisma/prisma", "TypeScript", 40000),
    ("supabase/supabase", "TypeScript", 75000),
    ("astral-sh/ruff", "Rust", 35000),
    ("anthropics/claude-code", "TypeScript", 25000),
]

MODELS = ["claude", "openai_codex", "gemini"]
MODEL_WEIGHTS = [0.45, 0.30, 0.25]  # Approximate market share


def generate_sample_data(num_days=30):
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date()

    for i in range(num_days, 0, -1):
        date = today - timedelta(days=i)
        date_str = date.isoformat()

        commits = []
        totals = {m: 0 for m in MODELS}
        day_factor = 1 + (num_days - i) * 0.03  # Slight upward trend

        for repo, lang, stars in REPOS:
            # Each repo gets a random number of AI commits per day
            base = random.randint(0, 8)
            n_commits = int(base * day_factor)

            for _ in range(n_commits):
                model = random.choices(MODELS, weights=MODEL_WEIGHTS, k=1)[0]
                commits.append({
                    "sha": f"{random.randint(0, 0xFFFFFFFF):08x}",
                    "repo": repo,
                    "model": model,
                    "date": f"{date_str}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:00Z",
                    "language": lang,
                    "stars": stars,
                })
                totals[model] += 1

        # Simulate repo commit activity (total weekly commits including human)
        # AI commits are a small fraction of total — typically 1-15%
        repo_activity = {}
        repos_with_commits = {c["repo"] for c in commits}
        for repo, lang, stars in REPOS:
            if repo in repos_with_commits:
                # Higher-star repos tend to have more total commits
                base_weekly = random.randint(30, 200) + (stars // 10000) * 5
                repo_activity[repo] = {"weekly_total": base_weekly}

        snapshot = {
            "date": date_str,
            "commits": commits,
            "totals": totals,
            "repos_tracked": len(repos_with_commits),
            "repo_activity": repo_activity,
        }

        path = DAILY_DIR / f"{date_str}.json"
        with open(path, "w") as f:
            json.dump(snapshot, f, indent=2)

    print(f"Generated {num_days} days of sample data in {DAILY_DIR}")


if __name__ == "__main__":
    generate_sample_data()
