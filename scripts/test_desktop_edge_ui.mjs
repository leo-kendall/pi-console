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
 await call('browsingContext.setViewport',{context,viewport:{width:818,height:392},devicePixelRatio:2.75});
 await call('browsingContext.navigate',{context,url:'http://127.0.0.1:18777',wait:'complete'});await waitFor("page==='settings'");
 await evaluate("$('server-url').value='https://console.example.test';$('save-server').click();void 0");await waitFor("!$('pair').disabled");
 await evaluate("$('pair-code').value='ABCDEF12';$('pair').click();void 0");await waitFor('paired');
 await evaluate(`window.probeCalls=0;window.repaintCalls=0;window.copiedReport=null;window.testReads=0;
 const originalLocal=local;
 local=async(action,value)=>{if(action==='desktopProbe'){probeCalls++;return {available:true,sdk:35,layer:1,pixelCopy:0,columns:[]};}if(action==='desktopRepaint'){repaintCalls++;return {ok:true};}if(action==='copyDesktopReport'){copiedReport=JSON.parse(value);return {ok:true};}return originalLocal(action,value);};
 const frame=(...parts)=>parts.map(p=>String(p).length+'.'+p).join(',')+';';
 api=async(path,body)=>{
  if(path==='/api/desktop/open')return {id:'test-edge-display'};
  if(path.startsWith('/api/desktop/read/')){if(testReads++===0)return {data:frame('size',0,2560,1440)+frame('rect',0,0,0,2560,1440)+frame('cfill',14,0,34,34,34,255)+frame('sync',1)};await new Promise(r=>setTimeout(r,1000));return {data:frame('sync',testReads)};}
  return {ok:true};
 };
 navigate('desktop');setDeviceLandscape(true);$('resolution').value='2560,1440';$('desktop-connect').click();void 0`);
 await waitFor('desktopClient?.getDisplay().getWidth()===2560');
 for(const [i,[x,y]] of [[0,0],[2559,0],[0,1439],[2559,1439],[0,0]].entries()){
  await evaluate(`(()=>{const d=desktopClient.getDisplay(),s=d.getScale();desktopMouse.move({x:1280*s,y:720*s});desktopMouse.move({x:${x}*s,y:${y}*s});})()`);
  await waitFor('probeCalls==='+String(i+1));await delay(1300);
 }
 assert.equal(await evaluate('repaintCalls'),0,'Automatic edge capture must not explicitly repaint the WebView');
 assert.equal(await evaluate("document.body.classList.contains('desktop-controls-open')"),false,'Automatic edge capture must not open controls');
 assert.equal(await evaluate("$('sheet').open"),false);
 assert.equal(await evaluate('desktopEdgeProbe.snapshot().length'),4);
 await evaluate("$('desk-inspect').click();void 0");await waitFor("$('sheet').open");
 assert.equal(await evaluate('repaintCalls'),1);
 await evaluate("Array.from($('sheet-content').querySelectorAll('button')).find(b=>b.textContent==='复制诊断').click();void 0");await waitFor('copiedReport!==null');
 assert.equal(await evaluate('copiedReport.build'),21);assert.equal(await evaluate('copiedReport.edges.length'),4);
 assert.equal(await evaluate('copiedReport.edges.every(e=>e.sample.window.available&&e.sample.window.pixelCopy===0)'),true);
 const before=await evaluate('probeCalls');await evaluate("stopDesktop();desktopMouse.move({x:1,y:1});void 0");await delay(300);assert.equal(await evaluate('probeCalls'),before);
 console.log('Desktop input automatically captures all four corners with controls closed and no repaint; copied build-21 report includes bounded edge samples; disconnect prevents further capture (simulated desktop/native boundary).');
}finally{await evaluate('stopDesktop();pauseApp();void 0').catch(()=>{});await call('session.end');socket.close();}
