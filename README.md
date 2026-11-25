# AI Commit Tracker

A live dashboard that tracks AI-assisted commits across popular open-source repositories by detecting `Co-Authored-By` git trailers.

**[View the live dashboard](https://leonardl27.github.io/ai-commit-tracker/)**

## What it tracks

| AI Tool | Detection Pattern |
|---------|------------------|
| Claude (Anthropic) | `noreply@anthropic.com` |
| OpenAI Codex CLI | `noreply@openai.com` |
| Gemini Code Assist | `gemini-code-assist` |
| Cursor | `cursoragent@cursor.com` |

> **Note:** GitHub Copilot does not add `Co-Authored-By` trailers, so it is not tracked here. Some tools allow users to disable attribution, so actual usage may be higher than shown.

## Dashboard sections

- **Model Market Share** — doughnut chart + daily time series
- **Top 10 Repos** — stacked bar chart + table ranked by AI commit count
- **AI vs Human Commits** — estimated ratio using GitHub's commit activity stats
- **Rising Repos** — most active in the last 7 days
- **Language Breakdown** — AI commits by programming language

## How it works

1. **Collect** — `scripts/collect.py` queries the [GitHub Commit Search API](https://docs.github.com/en/rest/search/search#search-commits) for commits containing known AI tool email patterns. Only repos with 50+ stars are included.
2. **Generate** — `scripts/generate.py` aggregates daily snapshots into a summary JSON consumed by the frontend.
3. **Deploy** — A GitHub Actions workflow runs daily at 6 AM UTC, collects new data, regenerates the summary, and deploys to GitHub Pages.

## Local development

```bash
# Generate sample data for testing
python scripts/generate_sample.py

# Build the summary from daily snapshots
python scripts/generate.py

# Serve the site locally
cd site && python -m http.server 8080
```

Then open http://localhost:8080.

## Collecting real data

Requires a GitHub personal access token:

```bash
export GITHUB_TOKEN=ghp_your_token_here

# Collect yesterday's commits
python scripts/collect.py

# Collect a specific date
python scripts/collect.py --date 2026-02-28

# Backfill the last 30 days
python scripts/collect.py --backfill 30
```

## Project structure

```
├── .github/workflows/
│   └── daily-update.yml    # Daily cron: collect → generate → deploy
├── data/
│   └── daily/              # One JSON snapshot per day
├── scripts/
│   ├── collect.py          # GitHub API data collection
│   ├── generate.py         # Summary aggregation
│   ├── generate_sample.py  # Sample data for local testing
│   └── requirements.txt    # Python dependencies (requests)
└── site/
    ├── index.html          # Dashboard page
    ├── styles.css          # Styling
    ├── app.js              # Chart.js charts
    └── data.json           # Summary data consumed by frontend
```

## Tech stack

- **Frontend:** HTML, CSS, [Chart.js](https://www.chartjs.org/)
- **Backend:** Python scripts + GitHub Actions
- **Hosting:** GitHub Pages
