"""Conservative event-date collector for official Crossfire and NSTLGA sources.

Events only. Does not invent individual CS2 fixtures, scores, or stream times.
"""
from __future__ import annotations
import datetime as dt
import json
import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "events.json"
AGENT = "NA-CS2-Tracker/0.2.2 (+https://github.com/InventorofSoup/NA-CS-2-Tracker)"
SOURCES = (
    {"id":"crossfire-2026-season-7", "organizer_id":"crossfire", "organizer":"Crossfire",
     "name":"Crossfire Season 7", "source_url":"https://www.crossfire.to/",
     "fetch_urls":("https://raw.githubusercontent.com/CrossfireGG/Season-7/main/README.md",
                   "https://www.crossfire.to/"),
     "identity":(r"\bcrossfire\b",r"\bseason\s*0?7\b"),"year":2026},
    {"id":"nstlga-2026-black-pearl", "organizer_id":"nstlga", "organizer":"NSTLGA",
     "name":"NSTLGA Black Pearl Cup", "source_url":"https://www.nstlga.gg/events/black-pearl-cup",
     "fetch_urls":("https://www.nstlga.gg/events/black-pearl-cup",),
     "identity":(r"\bnstlga\b",r"\bblack\s+pearl\s+cup\b"),"year":2026}
)
MONTH = r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
SEP = r"(?:to|[-–—])"
TWO = re.compile(rf"\b(?P<m1>{MONTH})\.?\s+(?P<d1>\d{{1,2}})\s*{SEP}\s*(?P<m2>{MONTH})\.?\s+(?P<d2>\d{{1,2}})\s*,?\s*(?P<y>20\d{{2}})\b",re.I)
ONE = re.compile(rf"\b(?P<m1>{MONTH})\.?\s+(?P<d1>\d{{1,2}})\s*{SEP}\s*(?P<d2>\d{{1,2}})\s*,?\s*(?P<y>20\d{{2}})\b",re.I)
MONTHS = {x:i for i,x in enumerate(("jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"),1)}

def text_content(body, url):
    if url.lower().split("?",1)[0].endswith(".md"):
        text=body
    else:
        soup=BeautifulSoup(body,"html.parser")
        for elt in soup(["script","style","noscript","template"]):
            elt.decompose()
        text=soup.get_text(" ",strip=True)
    return re.sub(r"\s+"," ",text.replace("\u00a0"," ").replace("\u202f"," ")).strip()

def event_range(text, year):
    # Prefer the date range in the beginning of the official page, not unrelated rounds.
    lead = text[:2500]
    candidates = [(x.start(), x, False) for x in TWO.finditer(lead)]
    candidates += [(x.start(), x, True) for x in ONE.finditer(lead)]
    for _,match,same in sorted(candidates,key=lambda x:x[0]):
        if int(match.group("y"))!=year:
            continue
        m1=MONTHS[match.group("m1")[:3].lower()]
        m2=m1 if same else MONTHS[match.group("m2")[:3].lower()]
        try:
            start=dt.date(year,m1,int(match.group("d1")))
            end=dt.date(year,m2,int(match.group("d2")))
        except ValueError:
            continue
        if start<=end and (end-start).days<=100:
            return start.isoformat(),end.isoformat()
    raise ValueError("expected official event date range not found")

def parse_event(source, body, url):
    text=text_content(body,url)
    if not all(re.search(pattern,text,re.I) for pattern in source["identity"]):
        raise ValueError("official event identity not found")
    start,end=event_range(text,source["year"])
    return {
        "id":source["id"],"organizer_id":source["organizer_id"],"organizer":source["organizer"],
        "name":source["name"],"start_date":start,"end_date":end,
        "source_url":source["source_url"],"verification_url":url,
        "detail_level":"event_only","verified_at":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    }

def fetch_event(source, session=requests):
    errors=[]
    for url in source["fetch_urls"]:
        try:
            response=session.get(url,timeout=20,headers={"User-Agent":AGENT})
            response.raise_for_status()
            event=parse_event(source,response.text,url)
            print("Verified:",event["name"],"via",url)
            return event
        except (requests.RequestException,ValueError) as exc:
            errors.append(f"{url}: {exc}")
    raise ValueError("; ".join(errors))

def update_events(path=OUT,session=requests):
    prior=json.loads(path.read_text(encoding="utf8")) if path.exists() else []
    if not isinstance(prior,list):
        raise ValueError("existing events feed must be an array")
    known={}
    for old in prior:
        entry=dict(old)
        entry.setdefault("verification_url",entry.get("source_url"))
        known[entry["id"]]=entry
    failures=0
    checked=0
    for source in SOURCES:
        try:
            event=fetch_event(source,session)
            previous=known.get(event["id"])
            fields=("organizer","name","start_date","end_date","source_url","verification_url","detail_level")
            if previous and all(previous.get(k)==event.get(k) for k in fields):
                event["verified_at"]=previous.get("verified_at",event["verified_at"])
            known[event["id"]]=event
            checked+=1
        except ValueError as exc:
            failures+=1
            print(f"::warning title={source['organizer']} fetch failed::{exc}",file=sys.stderr)
    if not known:
        raise ValueError("No verified events; refusing to publish empty data")
    events=sorted(known.values(),key=lambda e:(e["start_date"],e["id"]))
    result=json.dumps(events,indent=2,ensure_ascii=False)+"\n"
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf8")!=result:
        temporary=path.with_suffix(path.suffix+".tmp")
        temporary.write_text(result,encoding="utf8")
        temporary.replace(path)
    print(f"Events: {len(events)} retained, {checked} checked successfully, {failures} source failures")
    return checked,failures

def main():
    try:
        _,failed=update_events()
    except (ValueError,OSError,json.JSONDecodeError) as exc:
        print(f"::error title=Event collector failed::{exc}",file=sys.stderr)
        return 1
    return 1 if failed else 0

if __name__=="__main__":
    sys.exit(main())
