"""Offline regression tests; external fetches are mocked, not passed off as live tests."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import requests
from collectors import discover_events as de
from collectors import update_matches as cm
from collectors.validate import check_match

CROSSFIRE_INDEX = '<html><h1>Crossfire Season 7</h1><p>Nov 2 to Dec 13, 2026</p></html>'
NSTLGA_INDEX = '''<html><a href="/events/black-pearl-cup">Black Pearl Cup DEC 8–18, 2026</a>
<a href="/events/emerald-cup">Emerald Cup OCT 16–18, 2026</a>
<a href="/events/texas-open-lan">Texas Open LAN OCT 30 – NOV 1, 2026</a></html>'''
BLACK = '<html><h1>NSTLGA Black Pearl Cup</h1><div>When DEC 8–18, 2026 Where Online</div><p>Registration open Nov 23</p></html>'
EMERALD = '<html><h1>NSTLGA Emerald Cup</h1><p>When OCT 16–18, 2026</p><div>Grand final Online</div><h2>Final</h2><div>Complete</div><b>LAG</b><p>def. EMPIRE 2–0</p></html>'
TEXAS = '<html><h1>NSTLGA Texas Open LAN</h1><p>When OCT 30 – NOV 1, 2026</p><h2>Final</h2><div>Complete</div><b>LAG</b><p>def. NuTorious 3–1</p></html>'
TEAM_CATEGORY = '<a href="/event/crossfire-season-7-playoffs/">CROSSFIRE Season 7 Playoffs</a>'
TEAM_PARENT = '<html><a href="/event/crossfire-season-7-playoffs-chicken-coop-vs-swole-patrol/">Chicken Coop vs Swole Patrol</a></html>'
TEAM_DETAILS = '''<html><h1>CROSSFIRE Season 7 Playoffs: Chicken Coop vs Swole Patrol</h1>
<div>November 15 @ 8:00 pm EST</div><p>CROSSFIRE Season 7 Playoffs Loss</p>
<div>Chicken Coop</div><span>0:2</span><p>BO3 · Forfeit</p><div>SP Swole Patrol</div>
<div>Date Sunday, November 15, 2026</div><div>Start 8:00 PM EST</div></html>'''
FIXTURE_URL = 'https://chickencoop.gg/event/crossfire-season-7-playoffs-chicken-coop-vs-swole-patrol/'


class Response:
    def __init__(self, body):
        self.text = body
        self.content = body.encode('utf8')
    def raise_for_status(self):
        pass


class Session:
    def __init__(self, pages):
        self.pages = pages
        self.visited = []
    def get(self, url, **kwargs):
        self.visited.append(url)
        value = self.pages.get(url, requests.ConnectionError('Offline test source'))
        if isinstance(value, Exception):
            raise value
        return Response(value)


def pages():
    return {
        de.CROSSFIRE_INDEX: CROSSFIRE_INDEX,
        de.NSTLGA_INDEX: NSTLGA_INDEX,
        'https://www.nstlga.gg/events/black-pearl-cup': BLACK,
        'https://www.nstlga.gg/events/emerald-cup': EMERALD,
        'https://www.nstlga.gg/events/texas-open-lan': TEXAS,
        cm.CROSSFIRE_CATEGORY: TEAM_CATEGORY,
        cm.KNOWN_CROSSFIRE_PARENT: TEAM_PARENT,
        FIXTURE_URL: TEAM_DETAILS,
    }


class DiscoverEventsTests(unittest.TestCase):
    def test_official_nstlga_link_allowlist(self):
        hostile = NSTLGA_INDEX + '<a href="https://evil.example/events/new">Fake</a>'
        urls = de.nstlga_links(hostile)
        self.assertEqual(len(urls), 3)
        self.assertTrue(all(x.startswith('https://www.nstlga.gg/events/') for x in urls))

    def test_cross_month_date_range(self):
        self.assertEqual(de.parse_date_range('OCT 30 – NOV 1, 2026'), ('2026-10-30', '2026-11-01'))

    def test_invalid_range_is_rejected(self):
        with self.assertRaises(ValueError):
            de.parse_date_range('DEC 88 – 99, 2026')

    def test_black_pearl_keeps_existing_id(self):
        self.assertEqual(de.parse_nstlga_event('https://www.nstlga.gg/events/black-pearl-cup', BLACK)['id'], 'nstlga-2026-black-pearl')

    def test_current_crossfire_season(self):
        self.assertEqual(de.parse_crossfire_event(CROSSFIRE_INDEX)['id'], 'crossfire-2026-season-7')

    def test_event_discovery_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'events.json'
            path.write_text('[]\n')
            de.update_events(path, Session(pages()), date(2026,11,18))
            first = path.read_text()
            self.assertEqual(len(json.loads(first)), 4)
            de.update_events(path, Session(pages()), date(2026,11,18))
            self.assertEqual(first, path.read_text())

    def test_partial_source_failure_preserves_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'events.json'
            de.update_events(path, Session(pages()), date(2026,11,18))
            original = json.loads(path.read_text())
            de.update_events(path, Session({de.NSTLGA_INDEX: requests.Timeout('test')}), date(2026,11,18))
            self.assertEqual(len(json.loads(path.read_text())), len(original))


class MatchCollectorTests(unittest.TestCase):
    def test_team_match_result_with_timezone(self):
        match = cm.parse_crossfire_fixture(FIXTURE_URL, TEAM_DETAILS)
        self.assertEqual((match['team_a'], match['team_b']), ('Chicken Coop','Swole Patrol'))
        self.assertEqual((match['score_a'],match['score_b'],match['status']), (0,2,'completed'))
        self.assertEqual(match['start_time'], '2026-11-15T20:00:00-05:00')
        check_match(match, {'crossfire','nstlga'})

    def test_unannounced_result_not_invented(self):
        html = TEAM_DETAILS.replace('Loss', 'Upcoming').replace('<span>0:2</span>', '<span>VS</span>')
        item = cm.parse_crossfire_fixture(FIXTURE_URL, html)
        self.assertEqual(item['status'], 'scheduled')
        self.assertIsNone(item['score_a'])

    def test_timezone_mismatch_rejected(self):
        # Nov 15 is standard time (EST), not daylight time (EDT).
        with self.assertRaises(ValueError):
            cm.parse_crossfire_fixture(FIXTURE_URL, TEAM_DETAILS.replace('EST','EDT'))

    def test_hostile_fixture_link_rejected(self):
        links = cm.crossfire_fixture_links(cm.KNOWN_CROSSFIRE_PARENT,
            '<a href="https://evil.example/event/crossfire-season-7-playoffs-team-a-vs-team-b/">Team A vs Team B</a>')
        self.assertEqual(links, [])

    def test_event_round_does_not_become_fixture(self):
        self.assertEqual(cm.crossfire_fixture_links(cm.KNOWN_CROSSFIRE_PARENT, TEAM_CATEGORY), [])

    def test_nstlga_finals_exact_time_not_invented(self):
        event = de.parse_nstlga_event('https://www.nstlga.gg/events/emerald-cup', EMERALD)
        match = cm.parse_nstlga_final(event, EMERALD)
        self.assertEqual((match['team_a'],match['team_b'],match['score_a'],match['score_b']),('LAG','EMPIRE',2,0))
        self.assertIsNone(match['start_time'])
        self.assertEqual(match['event_end_date'], '2026-10-18')
        check_match(match, {'nstlga'})

    def test_nstlga_black_pearl_has_no_fixture(self):
        event = de.parse_nstlga_event('https://www.nstlga.gg/events/black-pearl-cup', BLACK)
        self.assertIsNone(cm.parse_nstlga_final(event, BLACK))
        self.assertEqual(cm.sports_event_fixtures(event, BLACK), [])

    def test_structured_future_fixture_requires_exact_time(self):
        event = de.parse_nstlga_event('https://www.nstlga.gg/events/black-pearl-cup', BLACK)
        content = {'@context':'https://schema.org','@type':'SportsEvent','name':'Quarterfinal',
                   'homeTeam':{'name':'Team Alpha'},'awayTeam':{'name':'Team Beta'},
                   'startDate':'2026-12-09T18:00:00-08:00', 'url':'https://www.nstlga.gg/matches/black-pearl-alpha-beta'}
        html = '<script type="application/ld+json">'+json.dumps(content)+'</script>'
        fixtures = cm.sports_event_fixtures(event, html)
        self.assertEqual(len(fixtures),1)
        self.assertEqual(fixtures[0]['status'], 'scheduled')
        check_match(fixtures[0], {'nstlga'})
        content.pop('startDate')
        self.assertEqual(cm.sports_event_fixtures(event, '<script type="application/ld+json">'+json.dumps(content)+'</script>'), [])

    def test_sports_event_reschedule_keeps_stable_id(self):
        event = de.parse_nstlga_event('https://www.nstlga.gg/events/black-pearl-cup', BLACK)
        base = {'@type':'SportsEvent','homeTeam':{'name':'Team Alpha'},
                'awayTeam':{'name':'Team Beta'},
                'url':'https://www.nstlga.gg/matches/black-pearl-alpha-beta'}
        def fixture(time):
            return cm.sports_event_fixtures(event, '<script type="application/ld+json">'+json.dumps(
                {**base,'startDate':time})+'</script>')[0]
        self.assertEqual(fixture('2026-12-09T18:00:00-08:00')['id'],
                         fixture('2026-12-10T18:00:00-08:00')['id'])

    def test_live_collector_pipeline_with_mocked_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'matches.json'
            path.write_text('[]\n')
            count, observations, warnings = cm.update_matches(path, Session(pages()),date(2026,11,18))
            self.assertEqual((count, observations, warnings), (3,3,0))
            actual = json.loads(path.read_text())
            self.assertEqual({m['organizer_id'] for m in actual}, {'crossfire','nstlga'})
            self.assertEqual(sum(bool(m['start_time']) for m in actual), 1)
            snapshot = path.read_text()
            cm.update_matches(path, Session(pages()),date(2026,11,18))
            self.assertEqual(path.read_text(), snapshot)

    def test_total_source_failure_keeps_prior(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'matches.json'
            cm.update_matches(path, Session(pages()),date(2026,11,18))
            snapshot = path.read_text()
            count,observed,warnings = cm.update_matches(path, Session({}), date(2026,11,18))
            self.assertEqual((count,observed),(3,0))
            self.assertGreater(warnings,0)
            self.assertEqual(snapshot,path.read_text())

    def test_untimed_scheduled_match_is_rejected(self):
        event = de.parse_nstlga_event('https://www.nstlga.gg/events/emerald-cup', EMERALD)
        match = cm.parse_nstlga_final(event, EMERALD)
        match['status']='scheduled'
        with self.assertRaises(ValueError):
            check_match(match, {'nstlga'})


if __name__ == '__main__':
    unittest.main()
