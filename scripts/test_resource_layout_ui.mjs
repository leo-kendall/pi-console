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
 await evaluate("navigate('manage');void 0");await waitFor("testRequests.includes('/api/resources')");
 const states=['not-loaded','active/running','inactive/dead','activating/start','deactivating/stop','reloading/reload','maintenance','refreshing','failed/failed','not-found','unavailable','created','running','paused','restarting','removing','dead','exited','unknown','future-state','constructor','__proto__',null];
 await evaluate(`(async()=>{testResources=${JSON.stringify(states)}.map((state,i)=>({id:'long-'+i,name:'app-geoclue\\x2ddemo\\x2dagent@autostart.service-'+'continuous'.repeat(12),target:'unit-'+i+'.service',kind:'user',state,impact:'测试数据',control:false,logs:false}));await loadResources();})()`);
 await waitFor("$('resources').querySelectorAll('.resource-card').length===23");
 const errors=[];
 for(const width of [320,360,412,768]){
  await call('browsingContext.setViewport',{context,viewport:{width,height:900},devicePixelRatio:1});
  for(const dark of [false,true]){
   await evaluate(`document.body.classList.toggle('dark',${dark});void 0`);
   const report=JSON.parse(await evaluate(`JSON.stringify(Array.from($('resources').querySelectorAll('.resource-card')).map(card=>{const h=card.querySelector('h3'),b=card.querySelector('.badge'),r=card.getBoundingClientRect();return {title:h.textContent,titleOverflow:h.scrollWidth>h.clientWidth+1,cardRight:r.right,badgeRight:b.getBoundingClientRect().right,status:b.textContent};}))`));
   if(report.some(r=>r.titleOverflow||r.cardRight>width||r.badgeRight>width))errors.push('Name overflow at '+width+' dark='+dark);
   if(report.some(r=>!/[\u4e00-\u9fff]/.test(r.status)||/[a-z]/i.test(r.status)))errors.push('Untranslated status at '+width+' dark='+dark);
  }
 }
 assert.deepEqual(errors,[]);
 assert.equal(await evaluate("stateLabel('activating/start')"),'启动中');
 assert.equal(await evaluate("stateLabel('deactivating/stop')"),'停止中');
 assert.equal(await evaluate("stateLabel('paused')"),'已暂停');
 assert.equal(await evaluate("stateLabel('future-state')"),'状态未知');
 assert.equal(await evaluate("stateLabel(null)"),'状态未知');
 console.log('Long service names stay inside cards at 320/360/412/768 px in both themes; all service/container statuses including missing/unknown values display Chinese.');
}finally{await evaluate('pauseApp();void 0').catch(()=>{});await call('session.end');socket.close();}
