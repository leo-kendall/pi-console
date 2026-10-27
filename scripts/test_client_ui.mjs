// SPDX-License-Identifier: Apache-2.0
// Firefox BiDi integration against the explicitly simulated preview backend.
import assert from 'node:assert/strict';
const socket=new WebSocket('ws://127.0.0.1:19226/session');
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let serial=0;const waiting=new Map();
socket.onmessage=e=>{const m=JSON.parse(e.data),w=waiting.get(m.id);if(!w)return;waiting.delete(m.id);clearTimeout(w.timer);m.type==='error'?w.reject(Error(m.message)):w.resolve(m.result);};
function call(method,params={}){return new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>reject(Error('Timeout '+method)),20000);waiting.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));});}
await call('session.new',{capabilities:{alwaysMatch:{}}});
const context=(await call('browsingContext.getTree')).contexts[0].context;
async function evaluate(expression){const r=await call('script.evaluate',{expression,target:{context},awaitPromise:true});if(r.type==='exception')throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(expr){for(let i=0;i<80;i++){if(await evaluate(expr))return;await delay(100);}throw Error('Timeout: '+expr);}
try{
 await call('browsingContext.navigate',{context,url:'http://127.0.0.1:18777',wait:'complete'});
 await waitFor("page==='settings'");
 await evaluate(`window.clientCalls=[];window.clientProfiles=[{id:'a',name:'Home',url:'https://a.test',paired:true,active:true},{id:'b',name:'Lab',url:'https://b.test',paired:false,active:false}];window.clientActive='a';window.savedPiLocal=Pi.local;Pi.local=(id,a,v)=>{clientCalls.push([a,v]);let d={};if(a==='profiles')d={profiles:clientProfiles,active:clientActive};else if(a==='serverSettings')d={url:clientProfiles.find(p=>p.id===clientActive)?.url||'',profile:clientActive,paired:clientProfiles.find(p=>p.id===clientActive)?.paired||false};else if(a==='switchProfile'){clientActive=v;clientProfiles.forEach(p=>p.active=p.id===v);d={profiles:clientProfiles,active:v};}else if(a==='addProfile'){const p=JSON.parse(v);clientProfiles.push({id:'c',...p,paired:false});d={id:'c'};}else if(a==='removeProfile'){clientProfiles=clientProfiles.filter(p=>p.id!==v);d={profiles:clientProfiles,active:clientActive};}else if(a==='profileSettings')d={profile:clientActive,theme:clientActive==='b'?'dark':'light',frequency:3000};else if(a==='profileStatus')d={id:v,online:true};else if(a==='checkUpdate')d={current:'0.5.0-beta.2',available:true,version:'v0.6.0',notes:'<img src=x onerror=alert(1)>',downloadable:true,bytes:100};else if(a==='updateState')d={current:'0.5.0-beta.2',state:'ready',message:'Verified'};else return savedPiLocal(id,a,v);nativeResult(id,d,null);};void 0`);
 await evaluate(`new Promise((resolve,reject)=>{const s=document.createElement('script');s.src='profiles-ui.js';s.onload=resolve;s.onerror=reject;document.body.append(s)}).then(()=>true)`);
 await waitFor("!!$('server-profiles')");
 await evaluate('loadProfiles();void 0');await waitFor("document.querySelectorAll('[data-profile-id]').length===2");
 assert.equal(await evaluate("clientCalls.filter(c=>c[0]==='profileStatus').length"),0,'saved endpoints are not polled');
 await evaluate("document.querySelector('[data-profile-switch=\"b\"]').click();void 0");await waitFor("clientActive==='b'&&$('pair-state').textContent==='未配对'");
 assert.equal(await evaluate("document.body.classList.contains('dark')"),true,'profile-specific preferences restored');
 assert.equal(await evaluate('status===null&&history.length===0'),true,'old metrics cleared');
 await evaluate("document.querySelector('[data-profile-status=\"a\"]').click();void 0");await waitFor("document.querySelector('[data-profile-id=\"a\"]').textContent.includes('在线')");
 await evaluate("$('add-profile').click();void 0");await waitFor("!!$('profile-name')");
 await evaluate("$('profile-name').value='New';$('profile-url').value='https://c.test';$('profile-save').click();void 0");await waitFor('clientProfiles.length===3');
 await evaluate(`new Promise((resolve,reject)=>{const s=document.createElement('script');s.src='updates-ui.js';s.onload=resolve;s.onerror=reject;document.body.append(s)}).then(()=>true)`);
 await waitFor("!!$('update-check')");await evaluate("$('update-check').click();void 0");await waitFor("$('update-version').textContent.includes('0.6.0')");
 assert.equal(await evaluate("$('update-notes').textContent"),'<img src=x onerror=alert(1)>','release notes are plain text');
 assert.equal(await evaluate("$('update-notes').querySelector('img')===null"),true,'notes do not execute markup');
 await evaluate("$('update-download').click();void 0");await waitFor("clientCalls.some(c=>c[0]==='downloadUpdate')");
 assert.equal(await evaluate("clientCalls.some(c=>c[0]==='installUpdate')"),false,'download never auto-installs');
 await evaluate('loadUpdateState();void 0');await waitFor("!$('update-install').hidden");
 await evaluate("$('update-install').click();void 0");await waitFor("clientCalls.some(c=>c[0]==='installUpdate')");
 await evaluate("window.fastClientLocal=Pi.local;Pi.local=(id,a,v)=>{if(a==='checkUpdate')window.pendingUpdateCheck=id;else fastClientLocal(id,a,v);};$('update-check').click();void 0");
 await waitFor("!!window.pendingUpdateCheck");
 assert.equal(await evaluate("$('update-channel').disabled"),true,'channel cannot change during its pending check');
 await evaluate("nativeResult(pendingUpdateCheck,{current:'0.5.0-beta.2',available:false},null);void 0");
 await waitFor("!$('update-channel').disabled");
 console.log('Client browser: profile switches, settings isolation, demand-only status, add, release notes, explicit download/install passed');
}finally{await call('session.end');socket.close();}
