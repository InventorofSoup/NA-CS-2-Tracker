"""Collect source-verifiable NA Counter-Strike match records.

Crossfire coverage: public Chicken Coop team fixture pages, *not* the entire
FACEIT bracket. NSTLGA coverage: official final result on each recent event
page, plus structured SportsEvent fixtures if the organizer publishes them.
Do not infer an exact start time from a tournament day or bracket window.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collectors.discover_events import (
    HEADERS, NSTLGA_INDEX, EVENTS, get_html, nstlga_links, parse_nstlga_event,
)

OUT = ROOT / 'data' / 'matches.json'
CROSSFIRE_CATEGORY = 'https://chickencoop.gg/schedule/category/tournaments/crossfire/'
KNOWN_CROSSFIRE_PARENT = 'https://chickencoop.gg/event/crossfire-season-7-playoffs/'
TEAM_DOMAIN = 'chickencoop.gg'
SOURCE_KEYS = ('team_a','team_b','tournament','organizer_id','status','start_time','source_url','score_a','score_b','format','source_type','time_precision','event_end_date')


def canonical_team_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {TEAM_DOMAIN, f'www.{TEAM_DOMAIN}'}:
        return None
    if not re.fullmatch(r'/event/[a-z0-9-]+/?', parsed.path):
        return None
    return f'https://{TEAM_DOMAIN}{parsed.path.rstrip("/")}/'


def crossfire_parent_links(html):
    soup = BeautifulSoup(html, 'html.parser')
    results = set()
    for a in soup.select('a[href]'):
        url = canonical_team_url(urljoin(CROSSFIRE_CATEGORY, a['href']))
        if not url:
            continue
        slug = urlparse(url).path.strip('/')
        # A tournament page, not a team-vs-team fixture page.
        if re.fullmatch(r'event/crossfire-season-\d+(?:-playoffs)?', slug):
            results.add(url)
    return sorted(results)[:10]


def crossfire_fixture_links(parent_url, html):
    soup = BeautifulSoup(html, 'html.parser')
    results = set()
    for a in soup.select('a[href]'):
        text = ' '.join(a.get_text(' ', strip=True).split())
        url = canonical_team_url(urljoin(parent_url, a['href']))
        if not url or not re.search(r'\bvs\.?\b', text, re.I):
            continue
        if 'crossfire-season-' not in url or url == parent_url:
            continue
        results.add(url)
    return sorted(results)[:30]


def parse_crossfire_fixture(url, html):
    soup = BeautifulSoup(html, 'html.parser')
    h1 = soup.find('h1')
    if not h1:
        raise ValueError('Match title missing')
    title = ' '.join(h1.get_text(' ', strip=True).split())
    match = re.fullmatch(r'CROSSFIRE\s+Season\s+(\d{1,2})(?:\s+Playoffs)?\s*:\s*(.+?)\s+vs\.?\s+(.+)', title, re.I)
    if not match:
        raise ValueError('Not an individually announced Crossfire matchup')
    season = int(match.group(1))
    team_a, team_b = match.group(2).strip(), match.group(3).strip()
    if team_a.lower() == team_b.lower() or any(len(name) > 65 or len(name) < 2 for name in (team_a, team_b)):
        raise ValueError('Invalid opposing team names')
    text = ' '.join(soup.get_text(' ', strip=True).split())
    # The event detail shows 'November 15 @ 8:00 pm EST' and an exact
    # 'Sunday, November 15, 2026' date. Read both; don't use a bracket window.
    time_match = re.search(r'\b(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(?P<day>\d{1,2})\s*@\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<period>AM|PM)\s*(?P<tz>ET|EST|EDT)\b', text, re.I)
    full_date = re.search(r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(?P<day>\d{1,2}),?\s*(?P<year>20\d{2})\b', text, re.I)
    if not time_match or not full_date:
        raise ValueError('No confirmed individual match time and calendar date')
    if time_match['month'][:3].lower() != full_date['month'][:3].lower() or int(time_match['day']) != int(full_date['day']):
        raise ValueError('Page date and displayed start time disagree')
    month = next(n for n, name in enumerate(('jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'), 1) if name == time_match['month'][:3].lower())
    hour = int(time_match['hour']) % 12 + (12 if time_match['period'].lower() == 'pm' else 0)
    start = datetime(int(full_date['year']), month, int(time_match['day']), hour, int(time_match['minute']), tzinfo=ZoneInfo('America/New_York'))
    label = time_match['tz'].upper()
    if label in ('EST','EDT') and start.tzname() != label:
        raise ValueError('Published timezone conflicts with US Eastern daylight saving rules')

    status = 'scheduled'
    scores = (None, None)
    # A result is accepted only when the match page explicitly says Win/Loss
    # AND contains a matching map-score near that status.
    outcome = re.search(r'\b(Win|Loss)\b\s+' + re.escape(team_a) + r'\s+([0-5])\s*[:–-]\s*([0-5])\b', text, re.I)
    if outcome:
        status = 'completed'
        scores = (int(outcome.group(2)), int(outcome.group(3)))
        if scores[0] == scores[1] or (scores[0] > scores[1]) != (outcome.group(1).lower() == 'win'):
            raise ValueError('Winner/loser label conflicts with final score')

    return {
        'id': 'crossfire-team-' + hashlib.sha256(url.encode()).hexdigest()[:18],
        'team_a': team_a, 'team_b': team_b, 'tournament': f'Crossfire Season {season}',
        'organizer': 'Crossfire', 'organizer_id': 'crossfire', 'status': status,
        'start_time': start.isoformat(), 'score_a': scores[0], 'score_b': scores[1],
        'format': 'BO3' if re.search(r'\bBO3\b', text, re.I) else 'Format not published',
        'source_url': url, 'source_type': 'team schedule', 'time_precision': 'exact',
        'verified_at': datetime.now(timezone.utc).isoformat(timespec='seconds')
    }


def recent_nstlga_pages(session, today):
    pages = []
    for url in nstlga_links(get_html(NSTLGA_INDEX, session)):
        try:
            html = get_html(url, session)
            event = parse_nstlga_event(url, html)
            if date.fromisoformat(event['end_date']) >= today - timedelta(days=120):
                pages.append((event, html))
        except (requests.RequestException, ValueError, KeyError) as exc:
            print('::warning title=NSTLGA event page::' + str(exc).replace('\n',' '), file=sys.stderr)
    return pages


def parse_nstlga_final(event, html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script','style','noscript','template']):
        tag.decompose()
    text = ' '.join(soup.get_text(' ', strip=True).split())
    # Require the organizer's explicit 'Final Complete' result; ignore bracket
    # paths, stage standings and team rosters that could be misconstrued.
    final = re.search(r'\bFinal\s+Complete\s+(?P<a>[\w.\'& -]{2,55}?)\s+def\.\s+(?P<b>[\w.\'& -]{2,55}?)\s+(?P<sa>[0-5])\s*[–—-]\s*(?P<sb>[0-5])\b', text, re.I)
    if not final:
        return None
    team_a, team_b = final['a'].strip(), final['b'].strip()
    sa, sb = int(final['sa']), int(final['sb'])
    if not team_a or not team_b or team_a.lower() == team_b.lower() or sa <= sb:
        raise ValueError('Malformed NSTLGA final')
    return {
        'id': 'nstlga-' + hashlib.sha256(event['source_url'].encode()).hexdigest()[:18] + '-final',
        'team_a': team_a, 'team_b': team_b, 'tournament': event['name'],
        'organizer': 'NSTLGA', 'organizer_id': 'nstlga', 'status': 'completed',
        'start_time': None, 'score_a': sa, 'score_b': sb,
        'format': 'Grand final', 'source_url': event['source_url'],
        'source_type': 'organizer', 'time_precision': 'unpublished',
        'event_end_date': event['end_date'],
        'verified_at': datetime.now(timezone.utc).isoformat(timespec='seconds')
    }


def sports_event_fixtures(event, html):
    """Read only explicitly structured SportsEvent data, not inferred bracket slots."""
    soup = BeautifulSoup(html, 'html.parser')
    fixtures = []
    def visit(value):
        if isinstance(value, list):
            for child in value:
                visit(child)
            return
        if not isinstance(value, dict):
            return
        kind = value.get('@type', [])
        if isinstance(kind, str):
            kind = [kind]
        if 'SportsEvent' in kind:
            home, away = value.get('homeTeam'), value.get('awayTeam')
            def name(team):
                return team.get('name') if isinstance(team, dict) else team if isinstance(team, str) else None
            a, b = name(home), name(away)
            raw_time = value.get('startDate')
            if not a or not b or a == b or not isinstance(raw_time, str):
                return
            try:
                start = datetime.fromisoformat(raw_time.replace('Z', '+00:00'))
            except ValueError:
                return
            if start.tzinfo is None or len(a) > 70 or len(b) > 70:
                return
            # A fixture must belong to the actual published event time window.
            if not (event['start_date'] <= start.date().isoformat() <= event['end_date']):
                return
            # Require a stable fixture-specific URL or @id. Without this,
            # rescheduling the same teams would produce duplicate records.
            match_url = value.get('url') or value.get('@id')
            if not isinstance(match_url, str):
                return
            match_url = urljoin(event['source_url'], match_url)
            parsed = urlparse(match_url)
            if parsed.scheme != 'https' or parsed.hostname not in {'nstlga.gg','www.nstlga.gg'} or not parsed.path.startswith(('/events/', '/matches/')):
                return
            key = f"{event['id']}|{match_url}"
            fixtures.append({
                'id': 'nstlga-sports-' + hashlib.sha256(key.encode()).hexdigest()[:18],
                'team_a': a, 'team_b': b, 'tournament': event['name'], 'organizer': 'NSTLGA',
                'organizer_id': 'nstlga', 'status': 'scheduled', 'start_time': start.isoformat(),
                'score_a': None, 'score_b': None, 'format': 'Format not published',
                'source_url': match_url, 'source_type': 'organizer', 'time_precision': 'exact',
                'verified_at': datetime.now(timezone.utc).isoformat(timespec='seconds')
            })
        for child in value.values():
            if isinstance(child, (dict,list)):
                visit(child)
    for tag in soup.find_all('script', type='application/ld+json'):
        try:
            visit(json.loads(tag.string or tag.get_text()))
        except json.JSONDecodeError:
            continue
    return fixtures


def discover_crossfire_matches(session):
    links = set([KNOWN_CROSSFIRE_PARENT])
    warnings = []
    try:
        links.update(crossfire_parent_links(get_html(CROSSFIRE_CATEGORY, session)))
    except (requests.RequestException, ValueError) as exc:
        warnings.append(f'Team category: {exc}')
    results = []
    for parent in sorted(links):
        try:
            match_urls = crossfire_fixture_links(parent, get_html(parent, session))
            for url in match_urls:
                try:
                    results.append(parse_crossfire_fixture(url, get_html(url, session)))
                except (requests.RequestException, ValueError) as exc:
                    warnings.append(f'{url}: {exc}')
        except (requests.RequestException, ValueError) as exc:
            warnings.append(f'{parent}: {exc}')
    return results, warnings


def update_matches(path=OUT, session=requests, today=None):
    today = today or datetime.now(timezone.utc).date()
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    if not isinstance(old, list):
        raise ValueError('Existing match feed must be a JSON array')
    records = {record['id']: record for record in old}
    found = 0
    warnings = []
    new_records = []
    try:
        crossfire, cf_warnings = discover_crossfire_matches(session)
        new_records.extend(crossfire)
        warnings.extend(cf_warnings)
    except (requests.RequestException, ValueError) as exc:
        warnings.append(f'Crossfire: {exc}')
    try:
        for event, html in recent_nstlga_pages(session, today):
            try:
                final = parse_nstlga_final(event, html)
                if final:
                    new_records.append(final)
                new_records.extend(sports_event_fixtures(event, html))
            except (ValueError, KeyError) as exc:
                warnings.append(f"NSTLGA match data {event['source_url']}: {exc}")
    except (requests.RequestException, ValueError) as exc:
        warnings.append(f'NSTLGA discovery: {exc}')
    for record in new_records:
        prior = records.get(record['id'])
        # Do not erase an already verified result due to a temporary source
        # regression; flag it for review instead.
        if prior and prior.get('status') == 'completed' and record.get('status') != 'completed':
            warnings.append(f"Result regression ignored for {record['id']}")
            continue
        if prior and all(prior.get(k) == record.get(k) for k in SOURCE_KEYS):
            record['verified_at'] = prior.get('verified_at', record['verified_at'])
        records[record['id']] = record
        found += 1
    output = sorted(records.values(), key=lambda m: (m.get('start_time') or m.get('event_end_date') or '', m['id']))
    new = json.dumps(output, indent=2, ensure_ascii=False) + '\n'
    if output:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding='utf-8') != new:
            tmp = path.with_suffix('.json.tmp')
            tmp.write_text(new, encoding='utf-8')
            tmp.replace(path)
    elif not path.exists():
        # Allow a legitimate no-fixtures-yet state, with a conspicuous notice.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('[]\n', encoding='utf-8')
    for warning in warnings:
        print('::warning title=Match discovery::' + warning.replace('\n',' '), file=sys.stderr)
    print(f'Matches: {len(output)} retained; {found} verified observations; {len(warnings)} warnings')
    return len(output), found, len(warnings)


def main():
    try:
        update_matches()
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print('::error title=Match collector::' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
