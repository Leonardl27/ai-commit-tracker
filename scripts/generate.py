"""
Generate summary.json from daily snapshot files for the frontend dashboard.
Reads all data/daily/*.json files and produces data/summary.json.

Usage:
    python scripts/generate.py
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DAILY_DIR = DATA_DIR / "daily"
SITE_DIR = Path(__file__).resolve().parent.parent / "site"


def load_snapshots():
    """Load all daily snapshot files, sorted by date."""
    snapshots = []
    if not DAILY_DIR.exists():
        return snapshots

    for path in sorted(DAILY_DIR.glob("*.json")):
        with open(path) as f:
            snapshots.append(json.load(f))
    return snapshots


def generate_summary(snapshots):
    """Aggregate daily snapshots into a summary for the frontend."""
    if not snapshots:
        return {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "model_share_over_time": [],
            "top_repos": [],
            "rising_repos": [],
            "ai_vs_human": [],
            "language_breakdown": {},
            "totals": {"commits": 0, "repos": 0, "models": 0, "days_tracked": 0},
        }

    # Overall counters
    all_repos = set()
    all_models = set()
    repo_commits = defaultdict(lambda: defaultdict(int))  # repo -> model -> count
    repo_stars = {}
    repo_languages = {}
    language_model_counts = defaultdict(lambda: defaultdict(int))  # lang -> model -> count

    # Time series: daily counts per model
    model_share_over_time = []

    # For rising repos: count commits in last 7 days
    today = datetime.now(timezone.utc).date()
    seven_days_ago = (today - timedelta(days=7)).isoformat()
    recent_repo_commits = defaultdict(lambda: defaultdict(int))

    # Repo total commit activity (from stats API)
    repo_weekly_totals = defaultdict(list)  # repo -> list of weekly totals

    total_commits = 0

    for snapshot in snapshots:
        date = snapshot["date"]
        day_totals = snapshot.get("totals", {})

        # Time series data point
        model_share_over_time.append({
            "date": date,
            **{model: day_totals.get(model, 0) for model in ["claude", "cursor", "aider", "openai_codex"]},
        })

        for commit in snapshot.get("commits", []):
            repo = commit["repo"]
            model = commit["model"]
            lang = commit.get("language", "Unknown")
            stars = commit.get("stars", 0)

            all_repos.add(repo)
            all_models.add(model)
            repo_commits[repo][model] += 1
            repo_stars[repo] = max(repo_stars.get(repo, 0), stars)
            repo_languages[repo] = lang
            language_model_counts[lang][model] += 1
            total_commits += 1

            if date >= seven_days_ago:
                recent_repo_commits[repo][model] += 1

        # Collect repo activity data (total commits per week from stats API)
        for repo, activity in snapshot.get("repo_activity", {}).items():
            weekly = activity.get("weekly_total", 0)
            if weekly > 0:
                repo_weekly_totals[repo].append(weekly)

    # Top 10 repos by total AI commits
    repo_total = {repo: sum(models.values()) for repo, models in repo_commits.items()}
    top_repos = sorted(repo_total.items(), key=lambda x: x[1], reverse=True)[:10]
    top_repos_data = []
    for repo, count in top_repos:
        top_repos_data.append({
            "repo": repo,
            "total": count,
            "stars": repo_stars.get(repo, 0),
            "language": repo_languages.get(repo, "Unknown"),
            "by_model": dict(repo_commits[repo]),
        })

    # Top 10 rising repos (most commits in last 7 days)
    recent_total = {repo: sum(models.values()) for repo, models in recent_repo_commits.items()}
    rising = sorted(recent_total.items(), key=lambda x: x[1], reverse=True)[:10]
    rising_repos_data = []
    for repo, recent_count in rising:
        all_time = repo_total.get(repo, recent_count)
        rising_repos_data.append({
            "repo": repo,
            "recent": recent_count,
            "total": all_time,
            "stars": repo_stars.get(repo, 0),
            "language": repo_languages.get(repo, "Unknown"),
            "by_model": dict(recent_repo_commits[repo]),
        })

    # AI vs Human ratio for top repos
    # Use average weekly total * number of weeks tracked as an estimate of total commits
    ai_vs_human = []
    for repo in all_repos:
        ai_count = repo_total.get(repo, 0)
        weekly_samples = repo_weekly_totals.get(repo, [])
        if not weekly_samples or ai_count == 0:
            continue
        # Average weekly commits * number of weeks we tracked
        avg_weekly = sum(weekly_samples) / len(weekly_samples)
        num_weeks = max(len(snapshots) / 7, 1)
        estimated_total = int(avg_weekly * num_weeks)
        # Ensure total is at least as large as AI count
        estimated_total = max(estimated_total, ai_count)
        human_count = estimated_total - ai_count
        ai_pct = round(ai_count / estimated_total * 100, 1) if estimated_total > 0 else 0
        ai_vs_human.append({
            "repo": repo,
            "ai_commits": ai_count,
            "human_commits": human_count,
            "total_commits": estimated_total,
            "ai_percentage": ai_pct,
            "stars": repo_stars.get(repo, 0),
            "language": repo_languages.get(repo, "Unknown"),
        })
    # Sort by AI percentage descending, take top 10
    ai_vs_human.sort(key=lambda x: x["ai_percentage"], reverse=True)
    ai_vs_human = ai_vs_human[:10]

    # Language breakdown
    language_breakdown = {}
    for lang, models in sorted(language_model_counts.items(), key=lambda x: sum(x[1].values()), reverse=True)[:15]:
        language_breakdown[lang] = dict(models)

    # Today's commits (from most recent snapshot)
    latest = snapshots[-1] if snapshots else {}
    today_total = sum(latest.get("totals", {}).values())

    summary = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "model_share_over_time": model_share_over_time,
        "top_repos": top_repos_data,
        "rising_repos": rising_repos_data,
        "ai_vs_human": ai_vs_human,
        "language_breakdown": language_breakdown,
        "totals": {
            "commits": total_commits,
            "repos": len(all_repos),
            "models": len(all_models),
            "days_tracked": len(snapshots),
            "today": today_total,
        },
    }
    return summary


def main():
    print("Loading daily snapshots...")
    snapshots = load_snapshots()
    print(f"  Found {len(snapshots)} daily snapshot(s)")

    print("Generating summary...")
    summary = generate_summary(snapshots)

    # Write to data/summary.json
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = DATA_DIR / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Written to {summary_path}")

    # Also copy to site/ so the frontend can load it
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    site_summary_path = SITE_DIR / "data.json"
    with open(site_summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Copied to {site_summary_path}")

    print(f"  Total commits: {summary['totals']['commits']}")
    print(f"  Repos tracked: {summary['totals']['repos']}")
    print(f"  Days tracked: {summary['totals']['days_tracked']}")


if __name__ == "__main__":
    main()
