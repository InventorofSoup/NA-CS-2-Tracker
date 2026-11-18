"""Validate curated match JSON before publication. Standard-library only."""
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

root = Path(__file__).resolve().parents[1]
obj = json.loads((root / 'data' / 'matches.json').read_text(encoding='utf-8'))
assert isinstance(obj.get('matches'), list)
ids = set()
for match in obj['matches']:
    for field in ('id', 'event', 'team1', 'team2', 'status', 'tier', 'source_url'):
        assert isinstance(match.get(field), str) and match[field].strip(), f'Missing {field}: {match}'
    assert match['id'] not in ids, f'Duplicate ID: {match["id"]}'
    ids.add(match['id'])
    assert match['status'] in {'scheduled', 'live', 'finished', 'postponed', 'cancelled'}
    assert match['tier'] in {'pro', 'amateur', 'collegiate'}
    assert urlparse(match['source_url']).scheme in ('http', 'https')
    if match.get('start_time'):
        t = datetime.fromisoformat(match['start_time'].replace('Z', '+00:00'))
        assert t.tzinfo is not None, 'Start time requires timezone'
print(f'Validated {len(ids)} matches.')
