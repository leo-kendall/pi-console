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
 await call('browsingContext.setViewport',{context,viewport:{width:390,height:844},devicePixelRatio:1});
 await call('browsingContext.navigate',{context,url:'http://127.0.0.1:18777',wait:'complete'});
 await waitFor("page==='settings'");
 assert.equal(await evaluate("!!$('setup-guide')"),true,'new users get a connection guide');
 assert.equal(await evaluate("$('setup-guide').dataset.stage"),'address');
 assert.equal(await evaluate('testRequests.length'),0,'no unsolicited remote requests');
 assert.equal(await evaluate("$('connection').textContent"),'尚未配置服务器');
 await evaluate("$('server-url').value='https://demo.example.test/pi-console';$('server-url').dispatchEvent(new Event('input'));$('probe-server').click();void 0");
 await waitFor("$('connection-result').dataset.code==='ok'");
 assert.equal(await evaluate('testConnection.url'),'','probe must not save endpoint');
 await evaluate("$('server-url').value='https://other.example.test/pi-console';$('server-url').dispatchEvent(new Event('input'));void 0");
 assert.equal(await evaluate("$('connection-result').hidden"),true,'editing invalidates success');
 await evaluate("checkPaired();void 0");await delay(100);
 assert.equal(await evaluate("$('server-url').value"),'https://other.example.test/pi-console','settings refresh preserves unsaved draft');
 // A result for a previous draft must never be displayed as a result for a new draft.
 await evaluate("window.originalLocal=Pi.local;window.probeReply=null;Pi.local=(id,a,v)=>a==='probeServer'?(window.probeReply=()=>nativeResult(id,{ok:true,code:'ok',title:'模拟成功',detail:'模拟结果',elapsed_ms:1,http_status:200},null)):originalLocal(id,a,v);$('probe-server').click();void 0");
 await waitFor('probeReply!==null');
 await evaluate("$('server-url').value='https://new.example.test/pi-console';$('server-url').dispatchEvent(new Event('input'));probeReply();Pi.local=originalLocal;void 0");
 await delay(100);assert.equal(await evaluate("$('connection-result').hidden"),true,'stale probe result discarded');
 // A paused request cannot unlock the button for a newer in-flight probe.
 await evaluate("window.probeReplies=[];Pi.local=(id,a,v)=>a==='probeServer'?probeReplies.push(()=>nativeResult(id,{ok:true,code:'ok',title:'模拟结果',detail:'模拟数据',http_status:200,elapsed_ms:1},null)):originalLocal(id,a,v);$('probe-server').click();void 0");
 await waitFor('probeReplies.length===1');
 await evaluate("pauseSetup();$('probe-server').click();void 0");await waitFor('probeReplies.length===2');
 await evaluate('probeReplies[0]();void 0');await delay(100);
 assert.equal(await evaluate("$('probe-server').disabled"),true,'old completion cannot release new probe');
 await evaluate('probeReplies[1]();Pi.local=originalLocal;void 0');await waitFor("!$('probe-server').disabled");
 // A missing diagnostic endpoint does not lock an older backend out of pairing.
 await evaluate("Pi.local=(id,a,v)=>a==='probeServer'?nativeResult(id,{ok:false,code:'missing',title:'未找到连接检测接口',detail:'旧版后端可继续手动保存和配对',http_status:404,elapsed_ms:1},null):originalLocal(id,a,v);$('probe-server').click();void 0");
 await waitFor("$('connection-result').dataset.code==='missing'");
 assert.equal(await evaluate("$('save-server').disabled"),false);
 await evaluate("$('save-server').click();void 0");await waitFor("$('setup-guide').dataset.stage==='pair'");
 assert.equal(await evaluate('testConnection.url'),'https://new.example.test/pi-console');
 await evaluate("$('server-url').value='https://unsaved.example.test';$('server-url').dispatchEvent(new Event('input'));void 0");
 assert.equal(await evaluate("$('pair').disabled"),true,'cannot pair a newly typed address before saving it');
 await evaluate("$('server-url').value=testConnection.url;$('server-url').dispatchEvent(new Event('input'));void 0");
 await evaluate("$('pair-code').value='no';$('pair').click();void 0");
 assert.equal(await evaluate("$('pair-error').textContent.length>0"),true);
 await evaluate("$('pair-code').value='ABCDEF12';$('pair').click();void 0");await waitFor('paired');
 assert.equal(await evaluate("$('setup-guide').dataset.stage"),'verify');
 await evaluate("$('setup-check').click();void 0");await waitFor("!$('setup-finish').disabled");
 assert.equal(await evaluate("$('setup-checks').textContent.includes('未配置桌面')"),true);
 assert.equal(await evaluate("$('setup-checks').textContent.includes('不影响')"),true);
 // A live auth failure clears an earlier successful feature check.
 await evaluate("window.originalRequest=Pi.request;Pi.request=(id,m,p,b)=>p==='/api/status'?nativeResult(id,null,'请先配对当前服务器'):originalRequest(id,m,p,b);$('setup-check').click();void 0");
 await waitFor("$('setup-check-error').textContent.length>0");
 assert.equal(await evaluate("$('setup-finish').disabled"),true);
 await evaluate("Pi.request=originalRequest;$('setup-check').click();void 0");await waitFor("!$('setup-finish').disabled");
 // Already paired settings refresh preserves endpoint and the existing pairing.
 await evaluate("checkPaired();void 0");await delay(100);
 assert.equal(await evaluate('testConnection.paired'),true);
 assert.equal(await evaluate("$('setup-guide').dataset.stage"),'verify');
 // A late feature report cannot verify a removed pairing.
 await evaluate("window.checkReply=null;Pi.request=(id,m,p,b)=>p==='/api/setup'?(window.checkReply=()=>nativeResult(id,{checks:[]},null)):originalRequest(id,m,p,b);$('setup-check').click();void 0");
 await waitFor('checkReply!==null');
 await evaluate("testConnection.paired=false;checkPaired();void 0");await waitFor('!paired');
 await evaluate('checkReply();Pi.request=originalRequest;void 0');await delay(100);
 assert.equal(await evaluate("$('setup-finish').disabled"),true);
 await evaluate('testConnection.paired=true;checkPaired();void 0');await waitFor('paired');
 await evaluate("$('setup-check').click();void 0");await waitFor("!$('setup-finish').disabled");
 // Approximate enlarged Android text in the browser; this is not a handset test.
 await evaluate("(()=>{const nodes=[...document.querySelectorAll('#settings p,#settings b,#settings label,#settings button,#settings input,#settings small,#settings span,#settings h2,#settings li')],sizes=nodes.map(n=>parseFloat(getComputedStyle(n).fontSize));nodes.forEach((n,i)=>n.style.fontSize=(sizes[i]*1.4)+'px');})()");
 for(const width of [320,390,818]){
  await call('browsingContext.setViewport',{context,viewport:{width,height:844},devicePixelRatio:1});
  for(const dark of [false,true]){
   await evaluate(`document.body.classList.toggle('dark',${dark});document.body.classList.add('large-text');document.documentElement.style.fontSize='22px';void 0`);
   assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'),true,'no page overflow at '+width);
  }
 }
 await evaluate("$('setup-finish').click();void 0");await waitFor("page==='overview'");
 // A slow first settings read must preserve user input entered in the meantime.
 await evaluate("navigate('settings');window.settingsReply=null;Pi.local=(id,a,v)=>a==='serverSettings'?(window.settingsReply=()=>nativeResult(id,{url:'https://saved.example.test',paired:false},null)):originalLocal(id,a,v);delete $('server-summary').dataset.endpoint;$('server-url').value='';checkPaired();$('server-url').value='https://typed.example.test';$('server-url').dispatchEvent(new Event('input'));void 0");
 await waitFor('settingsReply!==null');await evaluate('settingsReply();Pi.local=originalLocal;void 0');await delay(100);
 assert.equal(await evaluate("$('server-url').value"),'https://typed.example.test');
 console.log('Setup guide: draft-only checks, stale results, pause races, legacy fallback, pairing, feature checks, auth failure, existing pairing and responsive layouts passed.');
}finally{await evaluate('pauseApp();void 0').catch(()=>{});await call('session.end');socket.close();}
