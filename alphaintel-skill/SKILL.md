---
name: alphaintel
description: "Production B2B intelligence pipeline: multi-source fetching, financial signal extraction, dashboard maintenance, and landing page ops."
version: 0.4
tags: [alphaintel, scraping, synthesis, signals, b2b, dashboard]
---

# AlphaIntel Skill (Production B2B)

Operate the AlphaIntel B2B intelligence product:
- Signal-backed dashboard (4 verticals)
- Multi-source scraper engine
- Landing page + waitlist
- Daily cron refresh
- Interactive signal cards with ticker links and expand/collapse

## Repo layout
- `sources/` — modular source fetchers + registry
- `sources/engine.py` — PipelineEngine orchestrator
- `sources/signals.py` — ticker extraction, event classification, market impact scoring
- `sources/markets_signals.py` — financial market depth: dark pool, FINRA short interest, crypto on-chain
- `update_dashboard.py` — CLI entrypoint, calls engine, handles backups/schema
- `data.json` — live dashboard payload
- `backups/` — rotated backups (gitignored)
- `index.html` — signal dashboard (filters, search, impact badges)
- `landing.html` — B2B landing page + waitlist
- `style.css` / `app.js` — production UI with interactive cards
- `terms.html` / `privacy.html` — legal placeholders

## Interactive card behavior
- Click card body or headline to expand/collapse bullets.
- Double-click any card to open source URL in new tab.
- Tickers are clickable links to Yahoo Finance quote page.
- Tab navigation works: focus card, Enter to expand, Escape to close.
- Source link opens directly to the original article.
- Impact badge color (HIGH/MEDIUM/LOW) plus confidence bar shown.

## Refresh data
```bash
cd C:\Users\bmtyg\nichaas
/c/Python313/python.exe update_dashboard.py
```
Exit codes: 0 success, 1 partial failure, 2 total failure.
Non-empty stderr triggers alerting in the cron job.

## Source registry
Adding a new source = create a `BaseSource` subclass in `sources/`, then import it
in `sources/__init__.py`.  The engine auto-discovers via registry.

Built-in sources (categories):
- finance: sec_edgar, yahoo_finance, central_banks, crypto_news, seeking_alpha, dark_pool, finra_short_interest, crypto_onchain
- security: cisa_kev, nvd_api, krebs_on_security, bleepingcomputer
- trends: tech_blogs_rss, tech_extra
- geopower: geopower, geopower_extra

## Signal taxonomy
- Tickers extracted via regex + stopword filter
- Event types: M&A, Termination, Partnership, Leadership, Bankruptcy, Regulatory Action, Public Market Event, Material Event
- Market impact score: 0-100 (high ≥75, medium ≥40)
- Confidence = blend of source reliability + event confidence + impact score

## Stripe checkout wiring
Starter/Pro cards use placeholder hrefs. Replace with real Stripe Payment Links:
- `href="https://buy.stripe.com/starter_link_placeholder"` → your Stripe $9/mo link
- `href="https://buy.stripe.com/pro_link_placeholder"` → your Stripe $19/mo link
Enterprise uses mailto: `bodea.mircea@gmail.com` until CRM is on.
Remove the `data-stripe` attribute once live.

## Waitlist form
Uses Formspree: `https://formspree.io/f/placeholder`
Replace with your Formspree / Netlify Forms / backend endpoint.
On submit, show inline success/error message; do not use alert().

## Deploy
```bash
cd C:\Users\bmtyg\nichaas
git add data.json index.html landing.html style.css app.js sources/ update_dashboard.py
git commit -m "feat: refresh AlphaIntel data + UI"
git push origin main
```
GitHub Pages publishes within ~60s.

## Monitoring
Cron job `aba12bfd2cef` runs daily at 06:00.
Manual trigger: `python update_dashboard.py`
Verify live: https://bmtyger.github.io/alphaintel/ (dashboard)
Landing: https://bmtyger.github.io/alphaintel/landing.html

## Anti-patterns
- Don’t bypass schema validation in production
- Don’t commit `backups/` or `__pycache__/`
- Don’t hardcode API keys in sources — use headers with contact email
- Don’t use followers/bots for credibility; build real analyst usage and testimonials
