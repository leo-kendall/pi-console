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
 await call('browsingContext.setViewport',{context,viewport:{width:360,height:800},devicePixelRatio:1});
 await call('browsingContext.navigate',{context,url:'http://127.0.0.1:18777',wait:'complete'});
 await waitFor("page==='settings'");
 await evaluate("$('server-url').value='https://console.example.test';$('save-server').click();void 0");await waitFor("!$('pair').disabled");
 await evaluate("$('pair-code').value='ABCDEF12';$('pair').click();void 0");await waitFor('paired');
 assert.equal(await evaluate("toolInfo.some(x=>x[0]==='devices')"),true,'Device management must be reachable from tools');
 await evaluate(`window.adminWrites=[];window.adminRole='admin';window.adminRows=[{id:'self',name:'我的手机',role:'admin',current:true,last_seen:1700000000},{id:'tablet',name:'平板',role:'viewer',current:false,last_seen:1700000000}];window.originalAdminApi=api;api=async(path,body)=>{if(path==='/api/session')return {id:'self',name:'我的手机',role:adminRole,current:true};if(path==='/api/devices')return {devices:adminRows};if(path==='/api/devices/rename'){adminWrites.push([path,body]);adminRows.find(x=>x.id===body.device).name=body.name;return {ok:true};}if(path==='/api/devices/role'||path==='/api/devices/revoke'||path==='/api/devices/pair-code'){adminWrites.push([path,body]);return {ok:true,code:'ABCD1234',expires_seconds:600,role:body.role};}if(path==='/api/grants')return {grants:[],system_helper_ready:false};if(path==='/api/resources')return {resources:[{id:'found-test',name:'长'.repeat(70),target:'test-app',kind:'container',identity:'a'.repeat(64),state:'running'}]};if(path==='/api/grants/set'||path==='/api/grants/remove'){adminWrites.push([path,body]);return {ok:true};}return originalAdminApi(path,body);};navigate('manage');openTool('devices');void 0`);
 await waitFor("$('tools-content').textContent.includes('平板')");
 assert.equal(await evaluate("$('tools-content').textContent.includes('只读')"),true);
 await evaluate("$('tools-content').querySelector('[data-device-rename=tablet]').click();void 0");
 await evaluate("$('sheet-content').querySelector('input').value='新平板';$('sheet-content').querySelector('.primary').click();void 0");
 await waitFor("adminWrites.some(x=>x[0]==='/api/devices/rename'&&x[1].name==='新平板')");
 await evaluate("openTool('grants');void 0");await waitFor("$('tools-content').querySelector('[data-edit-grant]')!==null");
 await evaluate("$('tools-content').querySelector('[data-edit-grant]').click();void 0");
 assert.equal(await evaluate('adminWrites.filter(x=>x[0].startsWith("/api/grants/")).length'),0);
 await evaluate("$('sheet-content').querySelector('input[value=stop]').checked=true;$('sheet-content').querySelector('.primary').click();void 0");
 await waitFor("adminWrites.some(x=>x[0]==='/api/grants/set')");
 assert.equal(await evaluate("adminWrites.find(x=>x[0]==='/api/grants/set')[1].identity"),'a'.repeat(64));
 assert.equal(await evaluate("adminWrites.find(x=>x[0]==='/api/grants/set')[1].rights.join(',')"),'stop');
 assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'),true);
 await evaluate("openTool('devices');void 0");await waitFor("$('tools-content').textContent.includes('添加设备')");
 await evaluate("[...$('tools-content').querySelectorAll('button')].find(b=>b.textContent==='生成一次性配对码').click();$('sheet-content').querySelector('.primary').click();void 0");
 await waitFor("$('sheet').open&&$('sheet-content').textContent.includes('ABCD1234')");
 await evaluate("$('sheet-close').click();void 0");
 await evaluate("adminRole='viewer';openTool('devices');void 0");await waitFor("$('tools-content').textContent.includes('只读')");
 assert.equal(await evaluate("$('tools-content').querySelector('[data-device-revoke]')===null"),true);
 console.log('Device management and exact-target grants: names, roles, confirmation, identity, viewer controls, 360px layout passed.');
}finally{await evaluate('pauseApp();void 0').catch(()=>{});await call('session.end');socket.close();}
