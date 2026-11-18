# NA CS2 Tracker — v2 event collector update

This is an **incremental update**. Upload the included files into the existing repository, preserving paths. Do not delete the existing index.html, style.css, app.js, data/matches.json, or data/sources.json.

## What it does

The scheduled GitHub Action fetches official Crossfire and NSTLGA event pages every three hours. It only publishes an event when the expected event identity and date range are found. It preserves previous verified data on temporary source failures and reports a failed run for investigation. It does **not** collect individual match fixtures or scores yet.

## Upload

1. Extract this ZIP.
2. In your repository root, use **Add file > Upload files** and drag the folders `collectors`, `data`, `.github` and this README into the upload area. Verify the resulting paths shown by GitHub. Hidden `.github` folders can be tricky in some file pickers; if it doesn't upload, create `.github/workflows/update-events.yml` using GitHub's **Add file > Create new file** editor and paste its contents.
3. Commit changes.
4. Open **Actions > Update verified NA CS2 events > Run workflow**. GitHub may first ask you to enable Actions.
5. Inspect the run logs and `data/events.json`. A green run means both source checks succeeded; red means at least one source needs attention.

## Important

The website's current frontend only reads `data/matches.json` and `data/sources.json`. This package establishes the **automated event data pipeline**; the event feed is not yet rendered in the website. The next version will display `data/events.json` in the tournament cards, and match-level collectors will follow when accessible, verified fixtures are available.

GitHub Actions scheduled runs can be delayed. The workflow needs repository write permissions to commit data; if the push fails, check repository **Settings > Actions > General > Workflow permissions** and select **Read and write permissions**, if available.

If a source changes its date format, update the source-specific parser after checking the official site. Never silently guess a fixture time.
