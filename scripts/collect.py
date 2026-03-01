"""
Collect AI-assisted commits from GitHub using the commit search API.
Detects Co-Authored-By trailers from known AI coding tools.

Usage:
    python scripts/collect.py                    # Collect yesterday's data
    python scripts/collect.py --date 2026-02-28  # Collect specific date
    python scripts/collect.py --backfill 30      # Backfill last N days

Requires GITHUB_TOKEN environment variable.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

GITHUB_API = "https://api.github.com"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "daily"

# AI tools detected via Co-Authored-By email domains
AI_MODELS = {
    "claude": "noreply@anthropic.com",
    "cursor": "cursoragent@cursor.com",
    "aider": "noreply@aider.chat",
    "openai_codex": "noreply@openai.com",
}

MIN_STARS = 50  # Filter out repos below this threshold


def get_session():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable is required.", file=sys.stderr)
        sys.exit(1)
    session = requests.Session()
    session.headers.update({
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.cloak-preview+json",
    })
    return session


def search_commits(session, email_domain, date_str):
    """Search GitHub for commits containing an AI tool's email in the message."""
    query = f'"{email_domain}" committer-date:{date_str}'
    url = f"{GITHUB_API}/search/commits"
    commits = []
    page = 1

    while True:
        params = {"q": query, "per_page": 100, "page": page, "sort": "committer-date"}
        resp = session.get(url, params=params)

        if resp.status_code == 403:
            # Rate limited — wait and retry
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - int(time.time()), 1)
            print(f"  Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue

        if resp.status_code == 422:
            # Validation error (e.g., date too far back)
            print(f"  Search validation error for {date_str}, skipping.")
            break

        resp.raise_for_status()
        data = resp.json()

        for item in data.get("items", []):
            repo_name = item.get("repository", {}).get("full_name", "")
            commit_data = {
                "sha": item.get("sha", ""),
                "repo": repo_name,
                "date": item.get("commit", {}).get("committer", {}).get("date", ""),
                "message_preview": item.get("commit", {}).get("message", "")[:120],
            }
            commits.append(commit_data)

        total = data.get("total_count", 0)
        fetched = page * 100
        if fetched >= total or fetched >= 1000 or not data.get("items"):
            break

        page += 1
        time.sleep(2)  # Be polite to the API

    return commits


def get_repo_info(session, repo_name, cache):
    """Fetch repo metadata (stars, language). Uses a cache to avoid repeat calls."""
    if repo_name in cache:
        return cache[repo_name]

    url = f"{GITHUB_API}/repos/{repo_name}"
    resp = session.get(url)

    if resp.status_code == 404:
        cache[repo_name] = None
        return None

    if resp.status_code == 403:
        reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
        wait = max(reset - int(time.time()), 1)
        print(f"  Rate limited on repo info, waiting {wait}s...")
        time.sleep(wait)
        return get_repo_info(session, repo_name, cache)

    resp.raise_for_status()
    data = resp.json()
    info = {
        "stars": data.get("stargazers_count", 0),
        "language": data.get("language") or "Unknown",
        "description": (data.get("description") or "")[:200],
    }
    cache[repo_name] = info
    return info


def get_repo_commit_activity(session, repo_name):
    """Fetch weekly commit activity for a repo. Returns total commits for the most recent week."""
    url = f"{GITHUB_API}/repos/{repo_name}/stats/commit_activity"

    for attempt in range(3):
        resp = session.get(url)

        if resp.status_code == 202:
            # GitHub is computing stats, wait and retry
            print(f"    Stats computing for {repo_name}, retrying...")
            time.sleep(3)
            continue

        if resp.status_code == 403:
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - int(time.time()), 1)
            print(f"    Rate limited on commit activity, waiting {wait}s...")
            time.sleep(wait)
            continue

        if resp.status_code in (404, 422):
            return None

        resp.raise_for_status()
        weeks = resp.json()
        if not weeks:
            return None

        # Return total commits for the most recent week
        return {"weekly_total": weeks[-1].get("total", 0)}

    return None


def collect_date(session, date_str):
    """Collect all AI-assisted commits for a single date."""
    print(f"Collecting data for {date_str}...")
    repo_cache = {}
    all_commits = []
    totals = {}

    for model, email in AI_MODELS.items():
        print(f"  Searching for {model} ({email})...")
        raw_commits = search_commits(session, email, date_str)
        print(f"    Found {len(raw_commits)} raw commits")

        filtered = []
        for commit in raw_commits:
            repo_name = commit["repo"]
            if not repo_name:
                continue

            info = get_repo_info(session, repo_name, repo_cache)
            if info is None or info["stars"] < MIN_STARS:
                continue

            filtered.append({
                "sha": commit["sha"],
                "repo": repo_name,
                "model": model,
                "date": commit["date"],
                "language": info["language"],
                "stars": info["stars"],
            })

        all_commits.extend(filtered)
        totals[model] = len(filtered)
        print(f"    After filtering (>={MIN_STARS} stars): {len(filtered)} commits")
        time.sleep(2)

    # Deduplicate by SHA (a commit could theoretically match multiple patterns)
    seen = set()
    unique_commits = []
    for c in all_commits:
        if c["sha"] not in seen:
            seen.add(c["sha"])
            unique_commits.append(c)

    # Fetch total commit activity for repos that had AI commits
    unique_repos = {c["repo"] for c in unique_commits}
    repo_activity = {}
    if unique_repos:
        print(f"  Fetching commit activity for {len(unique_repos)} repos...")
        for repo_name in unique_repos:
            activity = get_repo_commit_activity(session, repo_name)
            if activity:
                repo_activity[repo_name] = activity
            time.sleep(1)
        print(f"    Got activity for {len(repo_activity)} repos")

    snapshot = {
        "date": date_str,
        "commits": unique_commits,
        "totals": totals,
        "repos_tracked": len(unique_repos),
        "repo_activity": repo_activity,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / f"{date_str}.json"
    with open(output_path, "w") as f:
        json.dump(snapshot, f, indent=2)

    total_commits = sum(totals.values())
    print(f"  Saved {total_commits} commits across {snapshot['repos_tracked']} repos to {output_path}")
    return snapshot


def main():
    parser = argparse.ArgumentParser(description="Collect AI-assisted commit data from GitHub")
    parser.add_argument("--date", help="Collect data for a specific date (YYYY-MM-DD)")
    parser.add_argument("--backfill", type=int, help="Backfill the last N days")
    args = parser.parse_args()

    session = get_session()

    if args.backfill:
        today = datetime.now(timezone.utc).date()
        for i in range(args.backfill, 0, -1):
            date = today - timedelta(days=i)
            date_str = date.isoformat()
            output_path = DATA_DIR / f"{date_str}.json"
            if output_path.exists():
                print(f"Skipping {date_str} (already exists)")
                continue
            collect_date(session, date_str)
            time.sleep(5)  # Extra pause between days during backfill
    elif args.date:
        collect_date(session, args.date)
    else:
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        collect_date(session, yesterday)


if __name__ == "__main__":
    main()
