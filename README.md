# NA CS2 Tracker

**Beyond the Headliners.** An independent fan-made directory for North American Counter-Strike 2 matches.

## Status

This is the first frontend build. It is **not yet a live scraper**. The match feed starts empty intentionally: unverified schedules are not presented as real. The four organizer sources are listed as `planned` until their collectors have been implemented and tested. DFRAG is intentionally excluded from NA coverage.

## Local preview

Opening `index.html` directly as a file may prevent the browser from loading JSON. Use a local web server or GitHub Pages when ready. No applications are required to upload the files to GitHub.

## Add verified matches

Add objects to `data/matches.json`, with `id`, `team_a`, `team_b`, `tournament`, `organizer`, `organizer_id`, `status` (`scheduled`, `live`, `completed`), `start_time` (ISO 8601 with timezone), and `source_url` (direct HTTPS citation). Optional `format` is supported. Run `python collectors/validate.py` or rely on the included GitHub Actions validation workflow.

## Privacy and deployment

The repository can remain private. Do not enable GitHub Pages until you intend to publish the website; published Pages sites can be public even when repository source is private. No API keys should be committed.

## Planned collectors

Crossfire, ESEA/FACEIT, NSTLGA, and Fragadelphia. Future integrations should use official APIs or permitted sources, verify North American geography, normalize timezones, deduplicate matches, and preserve source attribution.

Not affiliated with Valve, FACEIT, ESEA, or any tournament organizer.
