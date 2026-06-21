---
name: alphaintel
description: "Production autonomous niche intelligence pipeline: fetch, validate, write dashboard data, and maintain backups."
version: 0.2
tags: [alphaintel, scraping, synthesis, dashboard, production]
---

# AlphaIntel Skill (Production)

Operate the AlphaIntel dashboard data pipeline with reliability guarantees:
schema validation, backup rotation, and structured logging.

## Goal
Produce fresh, structured JSON items for `data.json` covering targeted niches
(finance, security, trends by default) and push safely to production.

## Prereqs
- Python 3.11+ with stdlib only (no external deps)
- `data.json` schema enforced by `update_dashboard.py`
- Backups rotated automatically in `backups/`

## Workflow

### 1. Refresh data
Run the updater:
```bash
cd C:\Users\bmtyg\nichaas
/c/Python313/python.exe update_dashboard.py
```
This will:
- Fetch from CISA KEV, SEC EDGAR 8-K, Hacker News
- Validate every item against schema
- Back up previous `data.json` to `backups/`
- Write new `data.json`
- Log structured output to stdout

Exit codes:
- 0 = success
- 1 = partial failure (some sources failed, data was written)
- 2 = total failure (no data written)

### 2. Deploy
```bash
cd C:\Users\bmtyg\nichaas
git add data.json
git commit -m "feat: refresh AlphaIntel data"
git push origin main
```
GitHub Pages will publish within ~60 seconds.

### 3. Verify
- Open https://bmtyger.github.io/alphaintel/
- Confirm JSON schema loads without console errors
- Spot-check newest item timestamps

## Schema Constraints
Each intel item MUST have:
- category: one of `finance`, `security`, `trends`
- timestamp: ISO-ish string (e.g. "2026-06-21 14:43 UTC")
- headline: non-empty string
- bullet_points: array of strings (max 5 shown)
- source: string
- confidence: number 0-100

Breaking schema aborts the run (exit 2).

## Anti-patterns
- Do not invent sources or confidence scores
- Do not skip validation in production
- Do not delete backups manually unless rotating
- Do not modify `update_dashboard.py` to bypass schema

## Monitoring
Cron job `aba12bfd2cef` runs daily at 06:00. Non-empty stderr alerts the operator.
Manual trigger:
```bash
cd C:\Users\bmtyg\nichaas && /c/Python313/python.exe update_dashboard.py
```
