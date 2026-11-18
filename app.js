const $ = (id) => document.getElementById(id);
const safe = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
const safeUrl = (value) => {
  try { const url = new URL(String(value)); return url.protocol === 'https:' ? safe(url.href) : '#'; }
  catch { return '#'; }
};
const state = { matches: [], sources: [], events: [], eventsLoadError: false, query: '', organizer: '', status: '', view: 'all' };
const when = (iso) => {
  if (!iso) return 'Exact match time not published';
  try {
    const time = new Date(iso);
    return Number.isNaN(time.getTime()) ? 'Time unavailable' : new Intl.DateTimeFormat(undefined, {dateStyle:'medium', timeStyle:'short'}).format(time);
  } catch { return 'Time unavailable'; }
};
const eventDate = (day) => {
  if (!day) return 'Date unavailable';
  try { return new Intl.DateTimeFormat(undefined, {month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(new Date(`${day}T12:00:00Z`)); }
  catch { return 'Date unavailable'; }
};
const eventStatus = (event) => {
  const today = new Date().toISOString().slice(0, 10);
  if (today < event.start_date) return 'Upcoming';
  if (today > event.end_date) return 'Completed';
  return 'Event window underway';
};
const eventOrder = (a, b) => {
  const today = new Date().toISOString().slice(0, 10);
  const group = (e) => today <= e.end_date ? 0 : 1;
  if (group(a) !== group(b)) return group(a) - group(b);
  return group(a) === 0 ? a.start_date.localeCompare(b.start_date) : b.end_date.localeCompare(a.end_date);
};
const hasFutureTime = (match) => !!match.start_time && new Date(match.start_time).getTime() >= Date.now();
const isUpcoming = (match) => match.status === 'live' || (match.status === 'scheduled' && hasFutureTime(match));
const isPastUnconfirmed = (match) => match.status === 'scheduled' && !hasFutureTime(match);
const matchStatus = (match) => isPastUnconfirmed(match) ? 'RESULT UNCONFIRMED' : match.status.toUpperCase();
const matchTime = (match) => {
  if (match.start_time) return when(match.start_time);
  if (match.event_end_date) return `Exact match time unpublished · event ended ${eventDate(match.event_end_date)}`;
  return 'Exact match time not published';
};
const sortMatch = (a, b) => {
  const group = (m) => isUpcoming(m) ? 0 : isPastUnconfirmed(m) ? 1 : 2;
  const diff = group(a) - group(b);
  if (diff) return diff;
  const timestamp = (m) => Date.parse(m.start_time || (m.event_end_date ? `${m.event_end_date}T12:00:00Z` : '')) || 0;
  return group(a) === 0 ? timestamp(a) - timestamp(b) : timestamp(b) - timestamp(a);
};

function render() {
  $('total').textContent = state.matches.length;
  $('upcoming').textContent = state.matches.filter(isUpcoming).length;
  $('completed').textContent = state.matches.filter((m) => m.status === 'completed').length;
  $('organizers').textContent = state.sources.length;

  const query = state.query.toLowerCase();
  const list = state.matches.filter((m) =>
    (!query || [m.team_a, m.team_b, m.tournament, m.organizer].join(' ').toLowerCase().includes(query)) &&
    (!state.organizer || m.organizer_id === state.organizer) &&
    (!state.status || m.status === state.status) &&
    (state.view === 'all' || (state.view === 'upcoming' ? isUpcoming(m) : m.status === 'completed'))
  ).sort(sortMatch);
  $('shown').textContent = `(${list.length})`;
  $('match-list').innerHTML = list.length ? list.map((m) => {
    const hasScore = Number.isInteger(m.score_a) && Number.isInteger(m.score_b);
    const center = hasScore ? `${safe(m.score_a)} – ${safe(m.score_b)}` : 'VS';
    const attribution = m.source_type === 'organizer' ? 'Organizer source' : m.source_type === 'team schedule' ? 'Team-published source' : 'Published source';
    return `<article class="match">
      <div class="match-top"><span>${safe(m.tournament)} · ${safe(m.organizer)}</span><span class="pill">${safe(matchStatus(m))}</span></div>
      <div class="match-body"><span class="team">${safe(m.team_a)}</span><span class="versus">${center}</span><span class="team">${safe(m.team_b)}</span></div>
      <div class="match-foot"><span>${safe(matchTime(m))} · ${safe(m.format || 'Format unavailable')} · ${safe(attribution)}</span><a href="${safeUrl(m.source_url)}" target="_blank" rel="noopener noreferrer">Verify at source ↗</a></div>
    </article>`;
  }).join('') : '<div class="empty"><h3>No verified matches in this view</h3><p>Not every event has published teams, individual start times or final scores yet. Empty listings are not proof that no games are taking place.</p></div>';

  $('event-list').innerHTML = state.eventsLoadError
    ? '<div class="empty"><h3>Event feed unavailable</h3><p>Event data could not be loaded. Check GitHub Actions or try again later.</p></div>'
    : state.events.length
      ? [...state.events].sort(eventOrder).map((event) => `
        <article class="event"><h3>${safe(event.name)}</h3>
          <p>${safe(event.organizer)} · ${eventDate(event.start_date)} – ${eventDate(event.end_date)}</p>
          <p>${safe(eventStatus(event))} · Verified event dates, not a claim of a live match.</p>
          <a href="${safeUrl(event.source_url)}" target="_blank" rel="noopener noreferrer">Official event source ↗</a>
        </article>`).join('')
      : '<div class="empty"><h3>No verified events published yet</h3><p>Collector has not published confirmed event dates.</p></div>';

  $('source-list').innerHTML = state.sources.map((source) => {
    const count = state.matches.filter((match) => match.organizer_id === source.id).length;
    const hasEvents = state.events.some((event) => event.organizer_id === source.id);
    const label = count ? `${count} sourced matches · incomplete coverage` : hasEvents ? 'Event dates available · match coverage partial' : 'No verified listings yet';
    return `<div class="source-row"><strong>${safe(source.name)}</strong><span>${safe(label)}</span><a href="${safeUrl(source.url)}" target="_blank" rel="noopener noreferrer">Visit source ↗</a></div>`;
  }).join('');
}

async function boot() {
  try {
    const [matchesResponse, sourcesResponse] = await Promise.all([
      fetch('data/matches.json', {cache:'no-store'}), fetch('data/sources.json', {cache:'no-store'})
    ]);
    if (!matchesResponse.ok || !sourcesResponse.ok) throw Error('Unable to load match data');
    state.matches = await matchesResponse.json();
    state.sources = await sourcesResponse.json();
    if (!Array.isArray(state.matches) || !Array.isArray(state.sources)) throw Error('Invalid match/source data format');
    try {
      const eventsResponse = await fetch('data/events.json', {cache:'no-store'});
      if (!eventsResponse.ok) throw Error('Event feed unavailable');
      const events = await eventsResponse.json();
      if (!Array.isArray(events)) throw Error('Invalid event feed');
      state.events = events;
    } catch (error) { state.eventsLoadError = true; console.warn('Event feed unavailable:', error); }
    $('organizer').innerHTML = '<option value="">All organizers</option>' + state.sources.map((source) => `<option value="${safe(source.id)}">${safe(source.name)}</option>`).join('');
    render();
  } catch (error) {
    $('match-list').innerHTML = `<div class="empty"><h3>Unable to load data</h3><p>${safe(error.message)}. Open this site through GitHub Pages.</p></div>`;
  }
}
$('search').addEventListener('input', (event) => {state.query=event.target.value.trim(); render();});
$('organizer').addEventListener('change', (event) => {state.organizer=event.target.value; render();});
$('status').addEventListener('change', (event) => {state.status=event.target.value; render();});
$('reset').addEventListener('click', () => {
  state.query='';state.organizer='';state.status='';
  $('search').value='';$('organizer').value='';$('status').value='';render();
});
document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => {
  state.view=tab.dataset.view;
  document.querySelectorAll('.tab').forEach((candidate) => candidate.classList.toggle('active', candidate === tab));
  render();
}));
boot();
