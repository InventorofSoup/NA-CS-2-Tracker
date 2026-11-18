// DOM-lite smoke tests; does not substitute for a real browser test.
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'..','app.js'),'utf8');
const event={id:'crossfire-2026-season-7',organizer_id:'crossfire',organizer:'Crossfire',name:'Crossfire Season 7',start_date:'2026-11-02',end_date:'2026-12-13',source_url:'https://www.crossfire.to/'};
const sources=[{id:'crossfire',name:'Crossfire',url:'https://www.crossfire.to/',integration_status:'planned'}];
async function start(events){
 const ids=['total','upcoming','completed','organizers','shown','match-list','event-list','source-list','organizer','search','status','reset'];
 const el=Object.fromEntries(ids.map(id=>[id,{textContent:'',innerHTML:'',value:'',addEventListener(){}}]));
 const tabs=['all','upcoming','completed'].map(view=>({dataset:{view},classList:{toggle(){}},addEventListener(){}}));
 const files={'data/matches.json':[],'data/sources.json':sources,'data/events.json':events};
 const ctx={document:{getElementById:id=>el[id],querySelectorAll:q=>q==='.tab'?tabs:[]},fetch:async url=>({ok:files[url]!==null,json:async()=>files[url]}),URL,Date,Intl,Promise,console};
 vm.runInNewContext(code,ctx);
 await new Promise(resolve=>setImmediate(resolve));
 return el;
}
(async()=>{
 const first=await start([event]);
 assert.match(first['event-list'].innerHTML,/Crossfire Season 7/);
 assert.match(first['event-list'].innerHTML,/Event dates only/);
 assert.match(first['match-list'].innerHTML,/No verified matches/);
 assert.match(first['source-list'].innerHTML,/Verified event dates/);
 const empty=await start([]);
 assert.match(empty['event-list'].innerHTML,/No verified events/);
 const bad=await start([{...event,name:'<img src=x onerror=alert(1)>',source_url:'javascript:alert(1)'}]);
 assert(!bad['event-list'].innerHTML.includes('<img'));
 assert.match(bad['event-list'].innerHTML,/href="#"/);
 console.log('DOM-lite frontend smoke tests passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
