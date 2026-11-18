"""Discover NSTLGA tournaments and Crossfire's current season from organizer pages.

Conservative: only an organizer's own HTTPS event pages are accepted. Never guess
match fixtures from tournament or round dates. Additive; existing verified entries
are preserved if any external page becomes unavailable.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / 'data' / 'events.json'
HEADERS = {'User-Agent': 'NA-CS2-Tracker/0.3 (independent community project; https://github.com/InventorofSoup/NA-CS-2-Tracker)'}
NSTLGA_INDEX = 'https://www.nstlga.gg/events'
CROSSFIRE_INDEX = 'https://www.crossfire.to/'
MONTH = r'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?'
RANGE = re.compile(rf'\b(?P<m1>{MONTH})\.?\s*(?P<d1>\d{{1,2}})\s*(?:to|[\-–—])\s*(?:(?P<m2>{MONTH})\.?\s*)?(?P<d2>\d{{1,2}})\s*,?\s*(?P<y>20\d{{2}})\b', re.I)
MONTHS = {m: n for n, m in enumerate(('jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'), 1)}


def normalize(text):
    return re.sub(r'\s+', ' ', text.replace('\u00a0', ' ')).strip()


def html_text(soup):
    copy = BeautifulSoup(str(soup), 'html.parser')
    for tag in copy(['script', 'style', 'noscript', 'template']):
        tag.decompose()
    return normalize(copy.get_text(' ', strip=True))


def parse_date_range(value):
    for match in RANGE.finditer(value):
        y = int(match['y'])
        start_month = MONTHS[match['m1'][:3].lower()]
        end_month = MONTHS[match['m2'][:3].lower()] if match['m2'] else start_month
        try:
            start = date(y, start_month, int(match['d1']))
            # Handles the odd December-to-January crossover if a source publishes it.
            end_year = y + 1 if end_month < start_month else y
            end = date(end_year, end_month, int(match['d2']))
        except ValueError:
            continue
        if start <= end and (end - start).days <= 100:
            return start.isoformat(), end.isoformat()
    raise ValueError('Published date range not found')


def nstlga_links(page):
    soup = BeautifulSoup(page, 'html.parser')
    links = set()
    for anchor in soup.select('a[href]'):
        url = urljoin(NSTLGA_INDEX, anchor['href']).split('#', 1)[0].split('?', 1)[0].rstrip('/')
        parsed = urlparse(url)
        if parsed.scheme == 'https' and parsed.hostname in {'www.nstlga.gg', 'nstlga.gg'} and re.fullmatch(r'/events/[a-z0-9-]+', parsed.path):
            links.add(url)
    return sorted(links)[:30]


def parse_nstlga_event(url, html):
    slug = urlparse(url).path.split('/')[-1]
    soup = BeautifulSoup(html, 'html.parser')
    header = soup.find('h1')
    if header is None:
        raise ValueError('Event title missing')
    title = normalize(header.get_text(' ', strip=True))
    if not title.lower().startswith('nstlga ') or len(title) > 110:
        raise ValueError('Not an NSTLGA event page')
    text = html_text(soup)
    # Prefer the 'When' field at the top over dates mentioned in standings.
    when = re.search(r'\bWhen\s+(.{0,85})', text[:1500], re.I)
    start, end = parse_date_range(when.group(1) if when else text[:900])
    year = start[:4]
    event_id = 'nstlga-2026-black-pearl' if slug == 'black-pearl-cup' and year == '2026' else f'nstlga-{year}-{slug}'
    return {'id': event_id, 'organizer_id': 'nstlga', 'organizer': 'NSTLGA', 'name': title,
            'start_date': start, 'end_date': end, 'source_url': url, 'verification_url': url,
            'detail_level': 'event_only', 'verified_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}


def parse_crossfire_event(html):
    soup = BeautifulSoup(html, 'html.parser')
    text = html_text(soup)
    match = re.search(r'\bCrossfire\s+Season\s+(\d{1,2})\b', text[:5000], re.I)
    if not match:
        raise ValueError('Current Crossfire season not identified')
    season = int(match.group(1))
    # The landing page publishes the current season's date range before its title.
    start, end = parse_date_range(text[:900])
    year = start[:4]
    url = CROSSFIRE_INDEX
    return {'id': f'crossfire-{year}-season-{season}', 'organizer_id': 'crossfire',
            'organizer': 'Crossfire', 'name': f'Crossfire Season {season}',
            'start_date': start, 'end_date': end, 'source_url': url, 'verification_url': url,
            'detail_level': 'event_only', 'verified_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}


def get_html(url, session=requests):
    response = session.get(url, timeout=20, headers=HEADERS)
    response.raise_for_status()
    if len(response.content) > 2_000_000:
        raise ValueError('Source page too large')
    return response.text


def update_events(path=EVENTS, session=requests, today=None):
    today = today or datetime.now(timezone.utc).date()
    current = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    if not isinstance(current, list):
        raise ValueError('Existing events feed is not an array')
    existing = {event['id']: dict(event) for event in current}
    successes = 0
    failures = []

    # Crossfire independent of NSTLGA. A failing source cannot discard a success.
    try:
        candidate = parse_crossfire_event(get_html(CROSSFIRE_INDEX, session))
        existing = merge_event(existing, candidate)
        successes += 1
    except (requests.RequestException, ValueError, KeyError) as exc:
        failures.append(f'Crossfire: {exc}')

    try:
        links = nstlga_links(get_html(NSTLGA_INDEX, session))
        if not links:
            raise ValueError('No event links on official events page')
        successes += 1
        for url in links:
            try:
                event = parse_nstlga_event(url, get_html(url, session))
                # Retain the recent 120 days of results and every announced future event.
                if date.fromisoformat(event['end_date']) < today - timedelta(days=120):
                    continue
                existing = merge_event(existing, event)
            except (requests.RequestException, ValueError, KeyError) as exc:
                failures.append(f'NSTLGA {url}: {exc}')
    except (requests.RequestException, ValueError) as exc:
        failures.append(f'NSTLGA index: {exc}')

    if not existing:
        raise ValueError('No event data to preserve or publish')
    result = sorted(existing.values(), key=lambda event: (event['start_date'], event['id']))
    new = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding='utf-8') != new:
        temp = path.with_suffix('.json.tmp')
        temp.write_text(new, encoding='utf-8')
        temp.replace(path)
    for warning in failures:
        print('::warning title=Event discovery::' + warning.replace('\n',' '), file=sys.stderr)
    print(f'Event discovery: {len(result)} retained; {successes} index sources confirmed; {len(failures)} detail warnings')
    return successes, len(failures)


def merge_event(existing, candidate):
    old = existing.get(candidate['id'])
    if old and all(old.get(key) == candidate[key] for key in ('name', 'start_date','end_date','source_url','verification_url')):
        candidate['verified_at'] = old.get('verified_at', candidate['verified_at'])
    existing[candidate['id']] = candidate
    return existing


def main():
    try:
        update_events()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print('::error title=Event discovery failed::' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
