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
async function waitFor(expr){for(let i=0;i<60;i++){if(await evaluate(expr))return;await delay(100);}throw Error('Timeout: '+expr);}
try{
 await call('browsingContext.setViewport',{context,viewport:{width:412,height:915},devicePixelRatio:1});
 await call('browsingContext.navigate',{context,url:'http://127.0.0.1:18777',wait:'complete'});
 await waitFor("page==='settings'");assert.equal(await evaluate('testRequests.length'),0);
 await evaluate("$('server-url').value='https://console.example.test/pi-console';$('save-server').click();void 0");
 await waitFor("!$('pair').disabled");assert.equal(await evaluate("$('server-summary').textContent"),'https://console.example.test/pi-console');
 await evaluate("$('pair-code').value='ABCDEF12';$('pair').click();void 0");await waitFor('paired');
 await evaluate("navigate('overview');void 0");await waitFor('status!==null');assert.equal(await evaluate("$('temp').textContent"),'42.0');
 await evaluate("navigate('manage');void 0");await waitFor("$('resources').textContent.includes('尚未授权')");
 await evaluate("openTool('alerts');void 0");await waitFor("$('tools-content').textContent.includes('告警阈值')");
 assert.equal(await evaluate("$('tools-content').querySelectorAll('input[type=checkbox]').length"),0);
 await evaluate("openTool('storage');void 0");await waitFor("$('tools-content').querySelector('select')?.options.length===2");
 assert.equal(await evaluate("$('tools-content').querySelector('select').options[1].value"),'media');
 assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'),true);
 console.log('First-run server setup, pairing, overview, deny-by-default resources and dynamic alert/storage UI passed with explicit simulated data.');
}finally{await evaluate('pauseApp();void 0').catch(()=>{});await call('session.end');socket.close();}
