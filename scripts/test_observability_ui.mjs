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
 await waitFor("page==='settings'");
 await evaluate(`(async()=>{testConnection={url:'https://fixture.example.test',paired:true};await checkPaired();active=true;navigate('manage');
 window.logPolls=0;window.logMode='follow';window.nativeCaptures=[];window.notificationFixture={schema:1,enabled:true,recovery:true,quiet_start:'22:00',quiet_end:'07:00'};
 window.fixtureProcess={pid:45,ppid:1,start:123,name:'fixture',owner:'fixture',state:'S',rss_bytes:4096,virtual_bytes:8192,memory_percent:10,cpu_percent:5,elapsed_seconds:20,threads:1,exe:'/fixture',cgroup:'/fixture',can_close:false,reason:'test fixture'};
 const oldRequest=Pi.request,oldLocal=Pi.local;Pi.local=(id,action,value)=>{if(['logsExport','logsCopy'].includes(action)){nativeCaptures.push({action,value:JSON.parse(value)});nativeResult(id,{ok:true},null);}else if(action==='notificationSettings'){if(value)notificationFixture=JSON.parse(value);nativeResult(id,notificationFixture,null);}else oldLocal(id,action,value);};
 Pi.request=(id,method,path,body)=>{if(path==='/api/logs/tail'){logPolls++;const n=logPolls;setTimeout(()=>nativeResult(id,{lines:n===1?['INFO hello','ERROR broken','WARN wait']:['INFO heartbeat '+n],cursor:'a'.repeat(48),reset:n===1,sampled_at:Date.now()/1000},null),logMode==='slow'?500:0);}else if(path==='/api/processes/45')nativeResult(id,fixtureProcess,null);else if(path==='/api/processes/history'){window.lastProcessBody=JSON.parse(body);const now=Date.now()/1000;nativeResult(id,{pid:45,start:123,points:[{time:now-9,cpu_percent:5,rss_bytes:4096},{time:now-6,cpu_percent:null,rss_bytes:null},{time:now,cpu_percent:10,rss_bytes:8192}],ended:false},null);}else if(path==='/api/alerts/rules'){window.savedAlertRules=JSON.parse(body);nativeResult(id,{ok:true},null);}else oldRequest(id,method,path,body);};
 await new Promise((resolve,reject)=>{const s=document.createElement('script');s.src='observability-ui.js';s.onload=resolve;s.onerror=reject;document.body.append(s);});
 const style=document.createElement('link');style.rel='stylesheet';style.href='observability.css';document.head.append(style);})();`);
 await evaluate("showLogs({id:'photos',name:'Fixture logs'});void 0");await waitFor("$('log-rows').textContent.includes('ERROR broken')");
 await evaluate("$('log-pause').click();$('log-search').value='broken';$('log-search').dispatchEvent(new Event('input'));$('log-level').value='error';$('log-level').dispatchEvent(new Event('change'));void 0");
 assert.equal(await evaluate("$('log-rows').textContent"),'ERROR broken');
 const paused=await evaluate('logPolls');await delay(2200);assert.equal(await evaluate('logPolls'),paused);
 await evaluate("$('log-copy').click();$('log-export').click();void 0");await waitFor('nativeCaptures.length===2');
 assert.equal(await evaluate("nativeCaptures[0].value.text"),'ERROR broken');assert.equal(await evaluate("nativeCaptures[1].value.name"),'logs-photos.txt');
 await evaluate("$('log-pause').click();void 0");await waitFor('logPolls>1');
 await evaluate("$('sheet').close();void 0");await delay(50);const closed=await evaluate('logPolls');await delay(2200);assert.equal(await evaluate('logPolls'),closed);
 // A late response from a different server must never populate the new sheet.
 await evaluate("logMode='slow';showLogs({id:'photos',name:'Old server'});$('server-summary').dataset.endpoint='https://other.example.test';observabilityConnectionChanged('https://other.example.test',true);void 0");await delay(600);assert.equal(await evaluate("$('log-rows').textContent"),'暂无匹配日志');
 await evaluate("$('sheet').close();logMode='follow';showLogs({id:'photos',name:'Background'});pauseApp();void 0");await delay(2200);const background=await evaluate('logPolls');await delay(2200);assert.equal(await evaluate('logPolls'),background);
 await evaluate("$('sheet').close();active=true;history=[{time:10,temperature:40,cpu:15,memory:20,network:{eth0:{rx:2048,tx:512}}},{time:13,temperature:null,cpu:null,memory:30,network:{}},{time:30,temperature:45,cpu:80,memory:50,network:{eth0:{rx:4096,tx:1024}}}];$('interface').replaceChildren();const op=document.createElement('option');op.value='eth0';op.textContent='eth0';$('interface').append(op);navigate('overview');void 0");
 // Keep a fixed series after the automatic overview request finishes.
 await delay(200);await evaluate("history=[{time:10,cpu:15,network:{eth0:{rx:2048}}},{time:13,cpu:null,network:{}},{time:30,cpu:80,network:{eth0:{rx:4096}}}];$('history-metric').value='cpu';$('history-metric').dispatchEvent(new Event('change'));void 0");
 assert.equal(await evaluate("$('chart-readout').textContent"),'80.0%');
 await evaluate("drawChart(1);void 0");assert.ok((await evaluate("$('chart-readout').textContent")).includes('暂无读数'));
 await evaluate("$('history-metric').value='rx';$('history-metric').dispatchEvent(new Event('change'));void 0");assert.equal(await evaluate("$('chart-readout').textContent"),'4.0 KiB/s');
 await evaluate("navigate('manage');processData={processes:[fixtureProcess]};showProcessDetail(45);void 0");await waitFor("$('process-history-chart')!==null");await waitFor('window.lastProcessBody!==undefined');assert.equal(await evaluate('lastProcessBody.start'),123);
 await evaluate("$('process-history-metric').value='rss_bytes';$('process-history-metric').dispatchEvent(new Event('change'));void 0");assert.ok((await evaluate("document.querySelector('.process-history').textContent")).includes('8.0 KiB'));
 await evaluate("$('sheet').close();openTool('alerts');void 0");await waitFor("$('alert-debounce')!==null && $('notify-enabled')!==null");
 await evaluate("$('alert-debounce').value='2';$('alert-recovery').value='4';Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='保存连续采样规则').click();void 0");await waitFor('window.savedAlertRules!==undefined');assert.equal(await evaluate('savedAlertRules.debounce_samples'),2);assert.equal(await evaluate('savedAlertRules.recovery_samples'),4);
 await evaluate("$('notify-enabled').checked=false;$('notify-recovery').checked=false;$('notify-quiet_start').value='23:00';Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='保存本机提醒设置').click();void 0");await waitFor("notificationFixture.quiet_start==='23:00'");assert.equal(await evaluate('notificationFixture.enabled'),false);
 assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'),true);
 console.log('Live logs browser round: follow/pause/resume/search/level/copy/SAF export/close/background/server switch passed.');
 console.log('Monitoring browser round: metric units/gaps/readouts/process identity/debounce/recovery/phone quiet preferences passed.');
}finally{await evaluate('pauseApp();stopObservability();void 0').catch(()=>{});await call('session.end');socket.close();}
