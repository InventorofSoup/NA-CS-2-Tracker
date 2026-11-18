const $ = (id) => document.getElementById(id);
const safe = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = { matches: [], sources: [], query: '', organizer: '', status: '', view: 'all' };
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
  $('match-list').innerHTML = list.length ? list.map(m => `<article class="match"><div class="match-top"><span>${safe(m.tournament)} · ${safe(m.organizer)}</span><span class="pill">${safe(m.status.toUpperCase())}</span></div><div class="match-body"><span class="team">${safe(m.team_a)}</span><span class="versus">VS</span><span class="team">${safe(m.team_b)}</span></div><div class="match-foot"><span>${when(m.start_time)} · ${safe(m.format || 'Format TBD')}</span><a href="${safe(m.source_url)}" target="_blank" rel="noopener noreferrer">Verify at source ↗</a></div></article>`).join('') : '<div class="empty"><h3>No verified matches listed yet</h3><p>We are setting up approved feeds for North American leagues. No placeholder fixtures or fabricated scores are shown.</p></div>';
  $('event-list').innerHTML = state.sources.map(s => `<article class="event"><h3>${safe(s.name)}</h3><p>${safe(s.description)}</p><a href="${safe(s.url)}" target="_blank" rel="noopener noreferrer">Official source ↗</a></article>`).join('');
  $('source-list').innerHTML = state.sources.map(s => `<div class="source-row"><strong>${safe(s.name)}</strong><span>${safe(s.integration_status === 'planned' ? 'Collector planned · no automatic feed yet' : s.integration_status)}</span><a href="${safe(s.url)}" target="_blank" rel="noopener noreferrer">Visit source ↗</a></div>`).join('');
}
async function boot() {
  try {
    const [mr,sr] = await Promise.all([fetch('data/matches.json'),fetch('data/sources.json')]);
    if (!mr.ok || !sr.ok) throw Error('Unable to load match data');
    state.matches = await mr.json(); state.sources = await sr.json();
    if (!Array.isArray(state.matches) || !Array.isArray(state.sources)) throw Error('Invalid data format');
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
