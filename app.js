const $ = (id) => document.getElementById(id);
const safe = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = { matches: [], sources: [], events: [], eventsLoadError: false, query: '', organizer: '', status: '', view: 'all' };
const safeUrl = (value) => {
  try {
    const url = new URL(String(value));
    return url.protocol === 'https:' ? safe(url.href) : '#';
  } catch { return '#'; }
};
const eventDate = (value) => {
  try { return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(value + 'T12:00:00Z')); }
  catch { return 'Date unavailable'; }
};
const eventStatus = (event) => {
  const today = new Date().toISOString().slice(0,10);
  return today < event.start_date ? 'Upcoming' : today > event.end_date ? 'Completed' : 'Dates underway';
};
const when = (iso) => { try { return new Intl.DateTimeFormat(undefined,{dateStyle:'medium',timeStyle:'short'}).format(new Date(iso)); } catch { return 'Time unavailable'; } };
function render() {
  const total = state.matches.length;
  $('total').textContent = total;
  $('upcoming').textContent = state.matches.filter(m => m.status === 'scheduled').length;
  $('completed').textContent = state.matches.filter(m => m.status === 'completed').length;
  $('organizers').textContent = state.sources.length;
  const q = state.query.toLowerCase();
  const list = state.matches.filter(m => (!q || [m.team_a,m.team_b,m.tournament,m.organizer].join(' ').toLowerCase().includes(q)) && (!state.organizer || m.organizer_id === state.organizer) && (!state.status || m.status === state.status) && (state.view === 'all' || (state.view === 'upcoming' ? ['scheduled','live'].includes(m.status) : m.status === 'completed'))).sort((a,b) => new Date(a.start_time) - new Date(b.start_time));
  $('shown').textContent = `(${list.length})`;
  $('match-list').innerHTML = list.length ? list.map(m => `<article class="match"><div class="match-top"><span>${safe(m.tournament)} · ${safe(m.organizer)}</span><span class="pill">${safe(m.status.toUpperCase())}</span></div><div class="match-body"><span class="team">${safe(m.team_a)}</span><span class="versus">VS</span><span class="team">${safe(m.team_b)}</span></div><div class="match-foot"><span>${when(m.start_time)} · ${safe(m.format || 'Format TBD')}</span><a href="${safeUrl(m.source_url)}" target="_blank" rel="noopener noreferrer">Verify at source ↗</a></div></article>`).join('') : '<div class="empty"><h3>No verified matches listed yet</h3><p>We are setting up approved feeds for North American leagues. No placeholder fixtures or fabricated scores are shown.</p></div>';
  $('event-list').innerHTML = state.eventsLoadError
    ? '<div class="empty"><h3>Event feed unavailable</h3><p>Check the latest GitHub Actions run.</p></div>'
    : state.events.length ? [...state.events].sort((a,b) => a.start_date.localeCompare(b.start_date)).map(e => `<article class="event">
         <h3>${safe(e.name)}</h3>
         <p>${safe(e.organizer)} · ${eventDate(e.start_date)} – ${eventDate(e.end_date)}</p>
         <p>${eventStatus(e)} · Event dates only. Individual fixtures are not yet collected.</p>
         <a href="${safeUrl(e.source_url)}" target="_blank" rel="noopener noreferrer">Official event source ↗</a>
       </article>`).join('')
    : '<div class="empty"><h3>No verified events published yet</h3><p>Waiting for the first successful collector run.</p></div>';
  $('source-list').innerHTML = state.sources.map(s => `<div class="source-row"><strong>${safe(s.name)}</strong><span>${state.events.some(e => e.organizer_id === s.id) ? 'Verified event dates · match data pending' : 'Source integration pending'}</span><a href="${safeUrl(s.url)}" target="_blank" rel="noopener noreferrer">Visit source ↗</a></div>`).join('');
}
async function boot() {
  try {
    const [mr,sr] = await Promise.all([fetch('data/matches.json'),fetch('data/sources.json')]);
    if (!mr.ok || !sr.ok) throw Error('Unable to load match data');
    state.matches = await mr.json(); state.sources = await sr.json();
    if (!Array.isArray(state.matches) || !Array.isArray(state.sources)) throw Error('Invalid data format');
    try {
      const er = await fetch('data/events.json', { cache: 'no-store' });
      if (!er.ok) throw Error('Event feed unavailable');
      const events = await er.json();
      if (!Array.isArray(events)) throw Error('Invalid event feed');
      state.events = events;
    } catch (err) { state.eventsLoadError = true; console.warn('Event feed unavailable:', err); }
    $('organizer').innerHTML = '<option value="">All organizers</option>' + state.sources.map(s => `<option value="${safe(s.id)}">${safe(s.name)}</option>`).join('');
    render();
  } catch (err) { $('match-list').innerHTML = `<div class="empty"><h3>Unable to load data</h3><p>${safe(err.message)}. Open this site using a web server or GitHub Pages.</p></div>`; }
}
$('search').addEventListener('input', e => {state.query=e.target.value.trim();render();});
$('organizer').addEventListener('change', e => {state.organizer=e.target.value;render();});
$('status').addEventListener('change', e => {state.status=e.target.value;render();});
$('reset').addEventListener('click', () => {state.query='';state.organizer='';state.status='';$('search').value='';$('organizer').value='';$('status').value='';render();});
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click',()=>{state.view=t.dataset.view;document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===t));render();}));
boot();
