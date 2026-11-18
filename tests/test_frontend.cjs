// DOM-lite smoke tests. These do not claim to have exercised a real browser.
'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const EVENT = {
  id:'crossfire-2026-season-7',organizer_id:'crossfire',organizer:'Crossfire',
  name:'Crossfire Season 7',start_date:'2026-11-02',end_date:'2026-12-13',
  source_url:'https://www.crossfire.to/',detail_level:'event_only'
};
const SOURCES = [
  {id:'crossfire',name:'Crossfire',url:'https://www.crossfire.to/',integration_status:'planned'},
  {id:'nstlga',name:'NSTLGA',url:'https://www.nstlga.gg/',integration_status:'planned'}
];
const future = new Date(Date.now() + 86400000 * 2).toISOString();
const EXACT = {
  id:'a',team_a:'Chicken Coop',team_b:'Swole Patrol',tournament:'Crossfire Season 7',
  organizer:'Crossfire',organizer_id:'crossfire',status:'scheduled',start_time:future,
  source_url:'https://chickencoop.gg/event/crossfire-season-7-playoffs/',
  source_type:'team schedule',format:'BO3',score_a:null,score_b:null
};
const RESULT = {
  id:'b',team_a:'LAG',team_b:'EMPIRE',tournament:'NSTLGA Emerald Cup',
  organizer:'NSTLGA',organizer_id:'nstlga',status:'completed',start_time:null,
  event_end_date:'2026-10-18',source_url:'https://www.nstlga.gg/events/emerald-cup',
  source_type:'organizer',format:'Grand final',score_a:2,score_b:0
};
async function launch(eventsResponse, matchesResponse = []) {
  const ids = ['total','upcoming','completed','organizers','shown','match-list',
    'event-list','source-list','organizer','search','status','reset'];
  const nodes = Object.fromEntries(ids.map(id => [id, {
    textContent:'',innerHTML:'',value:'',handlers:{},addEventListener(name,fn){this.handlers[name]=fn;}
  }]));
  const tabs = ['all','upcoming','completed'].map(value => ({dataset:{view:value},handlers:{},
    classList:{toggle(){}},addEventListener(name,fn){this.handlers[name]=fn;}}));
  const content = {'data/matches.json':matchesResponse,'data/sources.json':SOURCES,'data/events.json':eventsResponse};
  const context = {
    document:{getElementById:(id)=>nodes[id],querySelectorAll:(selector)=>selector==='.tab'?tabs:[]},
    fetch:async url=>({ok:content[url]!==null,json:async()=>content[url]}),
    console,URL,Date,Intl,Promise
  };
  vm.runInNewContext(script,context,{filename:'app.js'});
  await new Promise(resolve=>setImmediate(resolve));
  return {nodes,tabs};
}
(async ()=>{
  assert.match(html,/InventorofSoup\/NA-CS-2-Tracker\/issues/);
  const empty = await launch([EVENT]);
  assert.equal(empty.nodes.total.textContent,0);
  assert.match(empty.nodes['match-list'].innerHTML,/No verified matches in this view/);
  assert.match(empty.nodes['event-list'].innerHTML,/Crossfire Season 7/);
  assert.match(empty.nodes['event-list'].innerHTML,/Verified event dates/);
  assert.match(empty.nodes['source-list'].innerHTML,/Event dates available/);

  const data = await launch([EVENT],[EXACT,RESULT]);
  assert.equal(data.nodes.total.textContent,2);
  assert.equal(data.nodes.upcoming.textContent,1);
  assert.equal(data.nodes.completed.textContent,1);
  assert.match(data.nodes['match-list'].innerHTML,/Chicken Coop/);
  assert.match(data.nodes['match-list'].innerHTML,/LAG/);
  assert.match(data.nodes['match-list'].innerHTML,/2 – 0/);
  assert.match(data.nodes['match-list'].innerHTML,/Exact match time unpublished/);
  assert.match(data.nodes['match-list'].innerHTML,/Team-published source/);
  data.tabs[1].handlers.click();
  assert.match(data.nodes['match-list'].innerHTML,/Chicken Coop/);
  assert(!data.nodes['match-list'].innerHTML.includes('LAG</span>'));
  data.tabs[2].handlers.click();
  assert.match(data.nodes['match-list'].innerHTML,/LAG/);
  assert(!data.nodes['match-list'].innerHTML.includes('Chicken Coop</span>'));

  const missingEvents = await launch(null);
  assert.match(missingEvents.nodes['event-list'].innerHTML,/Event feed unavailable/);

  const hostile = await launch([{...EVENT,name:'<img src=x onerror=alert(1)>',source_url:'javascript:alert(1)'}],
    [{...RESULT,team_a:'<script>bad()</script>',source_url:'javascript:alert(1)'}]);
  assert(!hostile.nodes['event-list'].innerHTML.includes('<img'));
  assert(!hostile.nodes['match-list'].innerHTML.includes('<script>'));
  assert.match(hostile.nodes['match-list'].innerHTML,/href="#"/);
  console.log('Frontend smoke tests passed: match scores, unknown times, filters, sources, escaping, event cards.');
})().catch(error=>{console.error(error);process.exitCode=1;});
