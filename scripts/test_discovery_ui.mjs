// SPDX-License-Identifier: Apache-2.0
// Optional Node 22+/Firefox BiDi smoke check against scripts/preview_ui.py.
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
async function waitFor(expr){for(let i=0;i<160;i++){if(await evaluate(expr))return;await delay(100);}throw Error('Timeout: '+expr);}
try{
 await call('browsingContext.navigate',{context,url:'http://127.0.0.1:18777',wait:'complete'});
 await waitFor("page==='settings'");
 await evaluate("$('server-url').value='https://console.example.test';$('save-server').click();void 0");
 await waitFor("!$('pair').disabled");
 await evaluate("$('pair-code').value='ABCDEF12';$('pair').click();void 0");await waitFor('paired');
 await evaluate("navigate('manage');void 0");await waitFor("testRequests.includes('/api/resources')");
 await evaluate("testResources=[{id:'found-new',name:'new-container',target:'new-container',kind:'container',state:'running',description:'New app',impact:'Read-only discovery',control:false,logs:false,configured:false,discovered:true}];void 0");
 await waitFor("$('resources').textContent.includes('new-container')");
 assert.equal(await evaluate("Array.from($('resources').querySelectorAll('.actions button')).every(b=>b.disabled)"),true);
 await evaluate("$('resource-search').value='does-not-exist';$('resource-search').dispatchEvent(new Event('input'));void 0");
 assert.equal(await evaluate("$('resources').querySelectorAll('.resource-card').length"),0);
 await evaluate("$('resource-search').value='';$('resource-search').dispatchEvent(new Event('input'));pauseApp();void 0");
 const before=await evaluate("testRequests.filter(p=>p==='/api/resources').length");
 await delay(11000);assert.equal(await evaluate("testRequests.filter(p=>p==='/api/resources').length"),before);
 await evaluate("testResources=[];resumeApp();void 0");await waitFor("$('resources').querySelectorAll('.resource-card').length===0");
 await evaluate("(async()=>{testResources=[{id:'worker',name:'Server A worker',target:'a.service',kind:'user',state:'active/running',impact:'A jobs stop',control:true,logs:true,configured:true}];await loadResources();})()");
 await waitFor("$('resources').textContent.includes('Server A worker')");
 await evaluate("(async()=>{testConnection.url='https://other.example.test';testResourceError=true;await checkPaired();await loadResources();})()");
 assert.equal(await evaluate("$('resources').querySelectorAll('.resource-card').length"),0);
 console.log('New objects appear without manual refresh; unconfigured controls disabled; search, pause and resume passed.');
}finally{await evaluate('pauseApp();void 0').catch(()=>{});await call('session.end');socket.close();}
