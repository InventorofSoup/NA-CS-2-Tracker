"""Network-free regression tests for event updates."""
import json
import tempfile
import unittest
from pathlib import Path
import requests
from collectors import update_events as c

CF_MD="# Crossfire GG\n**Online Tier 2 CS2 Tournament** | November 2 – December 13, 2026\n**Season 7 Dates:** November 2 – December 13, 2026"
CF_HTML="<h1>Crossfire Season 7</h1><p>Nov 2 to Dec 13, 2026</p>"
NS_HTML="<h1>NSTLGA Black Pearl Cup</h1><p>DEC 8–18, 2026</p>"

class Response:
    def __init__(self,text): self.text=text
    def raise_for_status(self): pass

class Session:
    def __init__(self,values): self.values=values;self.called=[]
    def get(self,url,**kwargs):
        self.called.append(url)
        value=self.values.get(url,requests.ConnectionError("Unavailable"))
        if isinstance(value,Exception): raise value
        return Response(value)

class CollectorTests(unittest.TestCase):
    def test_crossfire_markdown(self):
        event=c.parse_event(c.SOURCES[0],CF_MD,c.SOURCES[0]["fetch_urls"][0])
        self.assertEqual((event["start_date"],event["end_date"]),("2026-11-02","2026-12-13"))
    def test_crossfire_html_fallback(self):
        urls=c.SOURCES[0]["fetch_urls"]
        session=Session({urls[1]:CF_HTML})
        event=c.fetch_event(c.SOURCES[0],session)
        self.assertEqual(event["verification_url"],urls[1])
        self.assertEqual(session.called,list(urls))
    def test_nstlga(self):
        event=c.parse_event(c.SOURCES[1],NS_HTML,c.SOURCES[1]["fetch_urls"][0])
        self.assertEqual(event["end_date"],"2026-12-18")
    def test_changed_dates_are_detected(self):
        event=c.parse_event(c.SOURCES[0],CF_MD.replace("December 13","December 14"),c.SOURCES[0]["fetch_urls"][0])
        self.assertEqual(event["end_date"],"2026-12-14")
    def test_incorrect_event_identity_rejected(self):
        with self.assertRaises(ValueError):
            c.parse_event(c.SOURCES[0],"Crossfire Season 8 Nov 2 – Dec 13, 2026",c.SOURCES[0]["fetch_urls"][1])
    def test_bad_date_rejected(self):
        with self.assertRaises(ValueError):
            c.parse_event(c.SOURCES[1],"NSTLGA Black Pearl Cup Dec 48–88, 2026",c.SOURCES[1]["fetch_urls"][0])
    def test_source_failures_do_not_discard_good_data(self):
        session=Session({c.SOURCES[1]["fetch_urls"][0]:NS_HTML})
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"events.json"
            self.assertEqual(c.update_events(path,session),(1,1))
            data=json.loads(path.read_text())
            self.assertEqual([x["organizer_id"] for x in data],["nstlga"])
    def test_empty_and_failed_keeps_empty_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"events.json";path.write_text("[]\n")
            with self.assertRaises(ValueError):
                c.update_events(path,Session({}))
            self.assertEqual(path.read_text(),"[]\n")
    def test_known_data_preserved_after_partial_failure(self):
        first=c.parse_event(c.SOURCES[0],CF_MD,c.SOURCES[0]["fetch_urls"][0])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"events.json"
            path.write_text(json.dumps([first])+"\n")
            self.assertEqual(c.update_events(path,Session({c.SOURCES[1]["fetch_urls"][0]:NS_HTML})),(1,1))
            data=json.loads(path.read_text())
            self.assertEqual(len(data),2)
            self.assertEqual(next(x for x in data if x["organizer_id"]=="crossfire")["verified_at"],first["verified_at"])
    def test_unchanged_data_is_stable(self):
        session=Session({c.SOURCES[0]["fetch_urls"][0]:CF_MD,c.SOURCES[1]["fetch_urls"][0]:NS_HTML})
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"events.json"
            self.assertEqual(c.update_events(path,session),(2,0))
            original=path.read_bytes()
            self.assertEqual(c.update_events(path,session),(2,0))
            self.assertEqual(path.read_bytes(),original)
