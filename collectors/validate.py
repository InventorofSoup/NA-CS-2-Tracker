"""Validate manually curated or collector-generated match data before publication."""
import datetime
import json
from pathlib import Path
from urllib.parse import urlparse

root = Path(__file__).resolve().parents[1]
matches = json.loads((root / 'data/matches.json').read_text(encoding='utf-8'))
sources = json.loads((root / 'data/sources.json').read_text(encoding='utf-8'))
assert isinstance(matches, list) and isinstance(sources, list)
source_ids = {s['id'] for s in sources}
assert len(source_ids) == len(sources), 'Duplicate organizer ID'
for s in sources:
    assert urlparse(s['url']).scheme == 'https', f'Invalid organizer URL: {s}'
    assert s['integration_status'] in {'planned', 'manual', 'active'}, f'Invalid source status: {s}'
ids = set()
for m in matches:
    required = ('id','team_a','team_b','tournament','organizer','organizer_id','status','start_time','source_url')
    assert all(m.get(k) for k in required), f'Missing required field: {m}'
    assert m['id'] not in ids, f'Duplicate match ID: {m["id"]}'
    ids.add(m['id'])
    assert m['organizer_id'] in source_ids, f'Unknown organizer: {m["id"]}'
    assert m['status'] in {'scheduled','live','completed'}, f'Invalid status: {m["id"]}'
    assert urlparse(m['source_url']).scheme == 'https', f'Invalid source URL: {m["id"]}'
    assert datetime.datetime.fromisoformat(m['start_time'].replace('Z','+00:00')).tzinfo is not None, f'Timezone required: {m["id"]}'
print(f'Validated {len(matches)} sourced matches and {len(sources)} organizers.')
