"""Strict validation of verified tournament event dates."""
import datetime as dt
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
ROOT = Path(__file__).resolve().parents[1]
events = json.loads((ROOT / "data/events.json").read_text(encoding="utf8"))
sources = json.loads((ROOT / "data/sources.json").read_text(encoding="utf8"))
if not isinstance(events,list) or not isinstance(sources,list):
    raise ValueError("Event feed and sources must be arrays")
if not events and "--allow-empty" not in sys.argv[1:]:
    raise ValueError("Event feed is empty after collection")
known={s["id"] for s in sources}
ids=set()
for event in events:
    required=("id","organizer_id","organizer","name","start_date","end_date","source_url","verification_url","detail_level","verified_at")
    if not isinstance(event,dict) or not all(isinstance(event.get(k),str) and event[k] for k in required):
        raise ValueError("Event missing required fields")
    if event["id"] in ids:
        raise ValueError("Duplicate event ID")
    ids.add(event["id"])
    if event["organizer_id"] not in known or event["detail_level"]!="event_only":
        raise ValueError("Invalid event organizer or data level")
    for key in ("source_url","verification_url"):
        url=urlparse(event[key])
        if url.scheme!="https" or not url.netloc or url.username or url.password:
            raise ValueError(f"Unsafe {key}")
    start=dt.date.fromisoformat(event["start_date"])
    end=dt.date.fromisoformat(event["end_date"])
    if end<start or (end-start).days>100:
        raise ValueError("Invalid event range")
    timestamp=dt.datetime.fromisoformat(event["verified_at"].replace("Z","+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("Verified timestamp must have timezone")
print(f"Validated {len(events)} event-level records.")
