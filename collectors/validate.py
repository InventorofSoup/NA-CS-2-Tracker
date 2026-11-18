"""Validate independently sourced NA CS2 match records prior to publication."""
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def load_list(name):
    data = json.loads((ROOT / 'data' / name).read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError(f'{name} must be a JSON array')
    return data


def is_https(value):
    if not isinstance(value, str):
        return False
    p = urlparse(value)
    return p.scheme == 'https' and bool(p.hostname) and not (p.username or p.password)


def check_match(match, organizers):
    fields = ('id','team_a','team_b','tournament','organizer','organizer_id','status','source_url')
    if not isinstance(match, dict) or not all(isinstance(match.get(k), str) and match[k].strip() for k in fields):
        raise ValueError('Missing required match field')
    if match['team_a'].casefold() == match['team_b'].casefold():
        raise ValueError('A match cannot have the same team twice')
    if match['organizer_id'] not in organizers:
        raise ValueError('Unregistered organizer')
    if match['status'] not in {'scheduled','live','completed'}:
        raise ValueError('Invalid status')
    if not is_https(match['source_url']):
        raise ValueError('Match source must be an HTTPS URL')
    if match.get('source_type') is not None and match['source_type'] not in {'organizer','team schedule','manual'}:
        raise ValueError('Unrecognized source type')
    start = match.get('start_time')
    if start is None:
        if match['status'] != 'completed' or match.get('time_precision') != 'unpublished':
            raise ValueError('Missing exact start time is only allowed for completed results')
        if not isinstance(match.get('event_end_date'), str):
            raise ValueError('Completed untimed result needs an event date for context')
        dt.date.fromisoformat(match['event_end_date'])
    else:
        if not isinstance(start, str) or not start:
            raise ValueError('start_time must be an ISO timestamp')
        timestamp = dt.datetime.fromisoformat(start.replace('Z','+00:00'))
        if timestamp.tzinfo is None:
            raise ValueError('start_time must include timezone')
    score_a, score_b = match.get('score_a'), match.get('score_b')
    if (score_a is None) != (score_b is None):
        raise ValueError('Both scores must be available together')
    if score_a is not None:
        if not all(type(v) is int and 0 <= v <= 5 for v in (score_a,score_b)) or score_a == score_b:
            raise ValueError('Invalid final map score')
        if match['status'] != 'completed':
            raise ValueError('Non-final match cannot have final map scores')
    if start is None and score_a is None:
        raise ValueError('Untimed completed match must include an explicit result')
    if 'verified_at' in match:
        verified = dt.datetime.fromisoformat(match['verified_at'].replace('Z','+00:00'))
        if verified.tzinfo is None:
            raise ValueError('Verification timestamp must include timezone')


def main():
    sources = load_list('sources.json')
    matches = load_list('matches.json')
    ids = set()
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get('id'), str) or not source['id']:
            raise ValueError('Invalid organizer record')
        if source['id'] in ids:
            raise ValueError('Duplicate organizer ID')
        ids.add(source['id'])
        if not is_https(source.get('url')):
            raise ValueError('Invalid organizer URL')
        if source.get('integration_status') not in {'planned','manual','active'}:
            raise ValueError('Invalid organizer integration state')
    seen = set()
    for match in matches:
        check_match(match, ids)
        if match['id'] in seen:
            raise ValueError('Duplicate match ID: ' + match['id'])
        seen.add(match['id'])
    print(f'Validated {len(matches)} matches and {len(sources)} organizer sources.')


if __name__ == '__main__':
    main()
