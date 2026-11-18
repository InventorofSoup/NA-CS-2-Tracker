# NA CS2 Tracker

Independent, fan-made North American Counter-Strike 2 match tracker. Tagline: **Beyond the Headliners.**

## Current status

This is the **first frontend build**, not a working live aggregator. No unverified matches are displayed. Crossfire, ESEA/FACEIT, NSTLGA and Fragadelphia are registered as planned sources, but **no automated collectors are active yet**. Their websites and extraction permissions must be checked before implementation.

## Preview

Use GitHub Pages if supported for your repository, or a browser-based HTML preview environment that serves files over HTTP. Opening `index.html` directly from disk may block JSON fetches.

## Match schema

Add verified matches to `data/matches.json` using objects with `id`, `event`, `team1`, `team2`, `status`, `tier`, `source_url`, `start_time` (ISO 8601 with timezone), optional `format` and `organizer`. Update `updated_at` when importing verified data. Run `python collectors/validate.py` to check entries. The GitHub workflow validates on push; it does not scrape or publish matches.

## Design

Dark, restrained orange sports-data dashboard. No third-party fonts, trackers, frameworks, or API keys. All information from public sources should retain attribution.

## Safety and data quality

Only use permitted APIs or approved extraction. Never infer live status from the clock alone. Do not import unverified schedules, and do not imply comprehensive coverage.
