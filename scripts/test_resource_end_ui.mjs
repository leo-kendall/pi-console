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
 await call('browsingContext.navigate',{context,url:'http://127.0.0.1:18777',wait:'complete'});
 await waitFor("page==='settings'");
 await evaluate("$('server-url').value='https://console.example.test';$('save-server').click();void 0");await waitFor("!$('pair').disabled");
 await evaluate("$('pair-code').value='ABCDEF12';$('pair').click();void 0");await waitFor('paired');
 await evaluate("testResources=[{id:'found-new',name:'new-container',target:'new-container',kind:'container',state:'running',description:'App',impact:'Read only until confirmed',control:false,logs:false,configured:false,can_authorize_end:true}];navigate('manage');void 0");
 await waitFor("$('resources').querySelector('[data-authorize-end]')!==null");
 assert.equal(await evaluate('testPrepareCount+testEndCount'),0);
 await evaluate("$('resources').querySelector('[data-authorize-end]').click();void 0");await waitFor("$('sheet').open&&$('sheet-content').querySelector('.primary')!==null");
 assert.equal(await evaluate('testPrepareCount'),1);assert.equal(await evaluate('testEndCount'),0);
 await evaluate("$('sheet-close').click();void 0");assert.equal(await evaluate('testEndCount'),0);
 await evaluate("$('resources').querySelector('[data-authorize-end]').click();void 0");await waitFor("$('sheet').open&&testPrepareCount===2");
 await evaluate("const button=$('sheet-content').querySelector('.primary');button.click();button.click();void 0");
 await waitFor("testEndCount===1&&!$('sheet').open");
 assert.equal(await evaluate('testEndCount'),1);assert.equal(await evaluate("$('resources').querySelector('[data-authorize-end]')===null"),true);
 console.log('Discovered app confirmation: no execution during discovery/prepare/cancel, confirmed end once, stopped state refreshed.');
}finally{await evaluate('pauseApp();void 0').catch(()=>{});await call('session.end');socket.close();}
