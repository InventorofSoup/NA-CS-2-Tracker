"""Conservative event discovery for two official NA CS2 organizer pages.

Only publishes event-level dates. It never fabricates individual match times.
Dependencies: requests, beautifulsoup4. Run from repository root.
"""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'events.json'
SOURCES = [
    ('crossfire', 'Crossfire', 'Crossfire Season 7', 'https://www.crossfire.to/',
     r'Nov\s*2\s*(?:to|[-–])\s*Dec\s*13\s*,?\s*2026', '2026-11-02', '2026-12-13'),
    ('nstlga', 'NSTLGA', 'NSTLGA Black Pearl Cup', 'https://www.nstlga.gg/events/black-pearl-cup',
     r'DEC\s*8\s*[-–]\s*18\s*,?\s*2026', '2026-12-08', '2026-12-18'),
]


def parse_event(source, html):
    sid, organizer, title, url, date_pattern, start, end = source
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    text = soup.get_text(' ', strip=True)
    if not re.search(date_pattern, text, re.I):
        raise ValueError(f'{sid}: expected official event dates not found; manual review needed')
    if sid == 'crossfire' and not re.search(r'Season\s*(?:0?7|07)', text, re.I):
        raise ValueError('crossfire: event identity missing')
    if sid == 'nstlga' and not re.search(r'Black\s+Pearl', text, re.I):
        raise ValueError('nstlga: event identity missing')
    return {'id': sid + '-2026-' + ('season-7' if sid == 'crossfire' else 'black-pearl'),
            'organizer_id': sid, 'organizer': organizer, 'name': title,
            'start_date': start, 'end_date': end, 'source_url': url,
            'detail_level': 'event_only', 'verified_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}


def main():
    old = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else []
    existing = {e['id']: e for e in old}
    failures = []
    for source in SOURCES:
        try:
            response = requests.get(source[3], timeout=25, headers={'User-Agent': 'NA-CS2-Tracker/0.2 (+https://github.com/InventorofSoup/NA-CS-2-Tracker)'})
            response.raise_for_status()
            event = parse_event(source, response.text)
            prior = existing.get(event['id'])
            if prior and all(prior.get(k) == event[k] for k in ('start_date', 'end_date', 'name', 'source_url')):
                event['verified_at'] = prior.get('verified_at', event['verified_at'])
            existing[event['id']] = event
            print('Verified event:', event['name'])
        except (requests.RequestException, ValueError) as exc:
            failures.append(f'{source[0]}: {exc}')
            print('WARNING:', failures[-1], file=sys.stderr)
    # Preserve previously verified entries when a source is temporarily unavailable.
    if not existing:
        raise SystemExit('No verified event data; refusing to publish empty output')
    output = sorted(existing.values(), key=lambda e: (e['start_date'], e['id']))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    new = json.dumps(output, indent=2, ensure_ascii=False) + '\n'
    if not OUT.exists() or OUT.read_text(encoding='utf-8') != new:
        OUT.write_text(new, encoding='utf-8')
    print(f'{len(output)} event(s) retained; {len(failures)} source error(s)')
    if failures:
        raise SystemExit('One or more sources failed; previous verified data preserved')


if __name__ == '__main__':
    main()
