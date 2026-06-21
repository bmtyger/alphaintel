---
name: alphaintel
description: "Autonomous niche intelligence pipeline: scrape/synthesize high-signal data, map to dashboard schema, write data.json for AlphaIntel."
version: 0.1
tags: [alphaintel, scraping, synthesis, dashboard]
---

# AlphaIntel Skill

Build and operate an autonomous data pipeline that feeds the AlphaIntel dashboard.

## Goal
Produce fresh, structured JSON items for `data.json` covering targeted niches (finance, security, trends by default) so the dashboard updates automatically.

## Output Schema
Each item must match:
```json
{
  "category": "finance|security|trends",
  "timestamp": "YYYY-MM-DD HH:MM UTC",
  "headline": "Short actionable headline",
  "bullet_points": ["concise point", "concise point"],
  "source": "Primary source name",
  "confidence": 85
}
```

## Workflow

### 1. Define or refresh niche focus
- Review current `data.json` categories.
- Adjust niche priorities if user requests a new vertical (e.g. biotech, energy).

### 2. Gather signals
Use web search + direct page extraction via browser tools:
- Search primary sources: SEC, CISA, SemiAnalysis, FT, BloombergNEF.
- Filter for high-signal items: funding, regulation, CVEs, benchmarks, partnerships.
- Discard low-signal / hyper-corporate PR unless strategically valuable.

### 3. Synthesize and structure
- 1 sentence headline + 2–3 bullets max
- Assign confidence score (82–99) based on source reliability and corroboration.
- Timestamp: current UTC or event time if backdating historical moves.

### 4. Write to data.json
- Preserve existing valid items; replace or dedupe stale ones.
- Maintain a target of 6–12 items unless user specifies otherwise.
- Write via `patch` or overwrite the file. Validate JSON before finishing.

### 5. Commit updates (optional)
```
git add data.json
git commit -m "feat: refresh AlphaIntel data"
git push origin main
```
Skip if user chooses manual media or deploy steps.

## Tooling
- `web_search` for broad discovery
- `web_extract` for direct page content
- `browser_navigate` + `browser_vision` when pages are dynamic/blocked
- `patch` / `write_file` for JSON updates
- `terminal` to run Python validators or git commands

## Anti-patterns
- Do not invent sources — name the actual reporter/registry.
- Avoid filler bullets; keep each item scannable.
- Do not break the JSON schema; missing fields break the dashboard.
- Do not scrape paywalled content when an official press release or filing is available.

## Sources
Real sources used by default:
- CISA Known Exploited Vulnerabilities catalog (security)
- SEC EDGAR current 8-K feed (finance)
- Hacker News frontpage RSS (trends)

## Verification
```bash
python -m json.tool data.json >/dev/null && echo JSON OK
```
