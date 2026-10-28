// SPDX-License-Identifier: Apache-2.0
'use strict';
(function(){
 if(window.Observability)return;
 const finite=v=>typeof v==='number'&&Number.isFinite(v), titles={temperature:'温度',cpu:'CPU 使用率',memory:'内存使用率',rx:'网络接收',tx:'网络发送',cpu_percent:'进程 CPU',rss_bytes:'进程内存 RSS'};
 function series(points,metric,iface){return points.filter(p=>finite(p.time)).map(p=>{let value=metric==='rx'||metric==='tx'?p.network?.[iface]?.[metric]:p[metric];return {time:p.time,value:finite(value)&&(metric==='temperature'||value>=0)?value:null};});}
 function segments(points){const result=[];let run=null,previous=null;for(const p of points){if(p.value===null){run=null;previous=null;continue;}if(!run||p.time-previous>12||p.time<=previous){run=[];result.push(run);}run.push(p);previous=p.time;}return result;}
 function bytes(n){return n>=1073741824?(n/1073741824).toFixed(1)+' GiB':n>=1048576?(n/1048576).toFixed(1)+' MiB':n>=1024?(n/1024).toFixed(1)+' KiB':n.toFixed(0)+' B';}
 function format(value,metric){if(!finite(value))return '暂无读数';return metric==='rx'||metric==='tx'?bytes(value)+'/s':metric==='rss_bytes'?bytes(value):value.toFixed(1)+(metric==='temperature'?'°C':'%');}
 function filterLines(lines,search,level){const q=search.trim().toLocaleLowerCase(),pattern={error:/\b(error|err|fatal|critical|crit|emerg|alert)\b/i,warning:/\b(warn|warning)\b/i,info:/\b(info|notice)\b/i,debug:/\b(debug|trace)\b/i}[level];return lines.filter(line=>(!q||line.toLocaleLowerCase().includes(q))&&(!pattern||pattern.test(line)));}
 function mergeLines(old,data){let rows=(data.reset?[]:old).concat(Array.isArray(data.lines)?data.lines.map(s=>String(s).slice(0,4096)):[]).slice(-1000),length=rows.reduce((n,s)=>n+s.length+1,0);while(rows.length&&length>65536){length-=rows[0].length+1;rows.shift();}return rows;}
 window.Observability={series,segments,format,filterLines,mergeLines};
 if(!document.getElementById('sheet'))return;
 let generation=0,logSession=null,processSession=null,endpoint='',metricChoice='temperature',chartIndex=-1;
 const serverKey=()=>document.getElementById('server-summary')?.dataset.endpoint||'';
 function stopSession(s){if(s){s.stopped=true;clearTimeout(s.timer);}}
 window.stopObservability=()=>{generation++;stopSession(logSession);stopSession(processSession);logSession=null;processSession=null;};
 window.observabilityConnectionChanged=(url,isPaired)=>{if(url!==endpoint||!isPaired){stopObservability();endpoint=url;}};
 const usable=s=>s&&!s.stopped&&s.generation===generation&&s.endpoint===serverKey()&&s.page===page&&active&&paired&&!document.hidden&&$('sheet').open&&s.box.isConnected&&$('sheet-content').contains(s.marker);
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stopObservability();});
 $('sheet').addEventListener('close',()=>stopObservability());
 new MutationObserver(()=>{if(logSession&&!$('sheet-content').contains(logSession.marker))stopSession(logSession);if(processSession&&!$('sheet-content').contains(processSession.marker))stopSession(processSession);}).observe($('sheet-content'),{childList:true});
 window.showLogs=function(resource){
  stopObservability();const box=sheet(resource.name+' · 实时日志'),marker=element('div',undefined,'live-logs'),search=element('input'),level=element('select'),pause=element('button','暂停','text-button'),copy=element('button','复制筛选结果','text-button'),save=element('button','导出筛选结果','text-button'),note=element('p','正在读取…','footnote'),pre=element('pre','', 'log-rows');
  search.type='search';search.placeholder='搜索已获取日志';search.setAttribute('aria-label','搜索日志');search.id='log-search';level.id='log-level';level.setAttribute('aria-label','日志级别');
  for(const [value,title]of[['all','所有级别'],['error','错误'],['warning','警告'],['info','信息'],['debug','调试']]){const option=element('option',title);option.value=value;level.append(option);}
  pause.id='log-pause';copy.id='log-copy';save.id='log-export';pre.id='log-rows';note.id='log-status';const controls=element('div',undefined,'observability-controls');controls.append(pause,copy,save);marker.append(search,level,controls,note,pre,element('p','每 2 秒检查一次，仅保留最近约 64 Ki 字符。级别按文本关键字识别；轮转或窗口丢失会重新载入。','footnote'));box.append(marker);
  const s=logSession={box,marker,endpoint:serverKey(),page,generation,rows:[],cursor:null,paused:false,loading:false,stopped:false,legacy:false,pending:null,lastPoll:0};
  const visible=()=>filterLines(s.rows,search.value,level.value);
  const render=()=>{pre.textContent=visible().join('\n')||'暂无匹配日志';copy.disabled=save.disabled=!visible().length;};search.oninput=level.onchange=render;
  pause.onclick=()=>{s.paused=!s.paused;pause.textContent=s.paused?'继续':'暂停';clearTimeout(s.timer);note.textContent=s.paused?'已暂停；搜索、复制和导出仍可用':'继续检查日志';if(!s.paused){if(s.pending){const data=s.pending;s.pending=null;applyData(data);}if(!s.paused)s.timer=setTimeout(poll,Math.max(0,2000-(Date.now()-s.lastPoll)));}};
  const capture=()=>({name:'logs-'+String(resource.id).replace(/[^A-Za-z0-9_-]/g,'_').slice(0,100)+'.txt',text:visible().join('\n')});
  copy.onclick=async()=>{if(s.endpoint!==serverKey())return;try{await local('logsCopy',{text:capture().text});toast('已复制筛选结果');}catch(e){toast(e.message);}};
  save.onclick=async()=>{if(s.endpoint!==serverKey())return;try{await local('logsExport',capture());toast('请选择保存位置');}catch(e){toast(e.message);}};
  function applyData(data){
    if(s.legacy){s.rows=mergeLines([],{reset:true,lines:String(data.text||'').split(/\r?\n/)});s.paused=true;pause.disabled=true;note.textContent='此后端仅支持日志快照；升级后可持续跟随';}
    else {s.rows=mergeLines(s.rows,data);s.cursor=data.cursor;note.textContent=(s.paused?'已暂停 · ':'跟随中 · ')+(data.reset?'已载入最新窗口 · ':'')+s.rows.length+' 行 · '+new Date(data.sampled_at*1000).toLocaleTimeString('zh-CN',{hour12:false});}
    render();
  }
  async function poll(){
   if(!usable(s)||s.paused||s.loading)return;s.loading=true;s.lastPoll=Date.now();
   try{const data=s.legacy?await api('/api/logs/'+encodeURIComponent(resource.id)):await api('/api/logs/tail',{resource:resource.id,cursor:s.cursor});if(!usable(s))return;
    if(s.paused)s.pending=data;else applyData(data);
   }catch(e){if(!usable(s))return;const message=String(e.message);if(!s.legacy&&/404|接口不存在|不支持|not found/i.test(message)){s.legacy=true;}else{note.textContent=message+'；已保留读到的日志';if(/403|未授权|无权限|denied|不允许/i.test(message)){s.paused=true;pause.textContent='继续';}}}
   finally{s.loading=false;if(usable(s)&&!s.paused){clearTimeout(s.timer);s.timer=setTimeout(poll,2000);}}
  }
  render();poll();return s;
 };
 function draw(canvas,points,key,iface,readout,index=-1){
  const width=canvas.clientWidth;if(!width)return;const height=112,dpr=window.devicePixelRatio||1;canvas.width=width*dpr;canvas.height=height*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);const css=getComputedStyle(document.body),accent=css.getPropertyValue('--accent').trim()||'#2679bd',muted=css.getPropertyValue('--muted').trim()||'#777',rows=series(points,key,iface),valid=rows.filter(p=>p.value!==null),percent=['cpu','memory'].includes(key),max=percent?100:Math.max(...valid.map(p=>p.value),1)*1.1,min=key==='temperature'?Math.min(0,...valid.map(p=>p.value)):0,start=rows[0]?.time||0,end=rows.at(-1)?.time||start;
  const x=p=>8+(p.time-start)/(end-start||1)*(width-16),y=p=>90-(p.value-min)/(max-min)*66;
  ctx.font='11px system-ui';ctx.fillStyle=muted;ctx.strokeStyle=css.getPropertyValue('--line').trim()||'#bbb';ctx.lineWidth=1;for(const yy of[24,57,90]){ctx.beginPath();ctx.moveTo(4,yy);ctx.lineTo(width-4,yy);ctx.stroke();}ctx.fillText(format(max,key),8,13);
  ctx.strokeStyle=accent;ctx.fillStyle=accent;ctx.lineWidth=2;for(const run of segments(rows)){ctx.beginPath();run.forEach((p,i)=>i?ctx.lineTo(x(p),y(p)):ctx.moveTo(x(p),y(p)));ctx.stroke();if(run.length===1){ctx.beginPath();ctx.arc(x(run[0]),y(run[0]),2,0,Math.PI*2);ctx.fill();}}
  if(!valid.length){ctx.fillStyle=muted;ctx.fillText('正在积累真实数据…',8,62);}
  if(index>=0&&rows.length){const p=rows[Math.min(rows.length-1,index)];readout.textContent=format(p.value,key)+' · '+new Date(p.time*1000).toLocaleTimeString('zh-CN',{hour12:false});if(p.value!==null){ctx.fillStyle=accent;ctx.beginPath();ctx.arc(x(p),y(p),4,0,Math.PI*2);ctx.fill();}}
  else readout.textContent=valid.length?format(valid.at(-1).value,key):'暂无读数';
 }
 const chart=$('chart');
 if(chart){const select=element('select');select.id='history-metric';select.setAttribute('aria-label','历史指标');for(const key of ['temperature','cpu','memory','rx','tx']){const option=element('option',titles[key]);option.value=key;select.append(option);}chart.before(select);select.onchange=()=>{metricChoice=select.value;chartIndex=-1;drawChart();};
  window.drawChart=function(index=-1){if(index>=0)chartIndex=index;draw(chart,history,metricChoice,$('interface')?.value,$('chart-readout'),chartIndex);$('chart-caption').textContent=titles[metricChoice]+'趋势 · 缺失采样保留间隔';chart.setAttribute('aria-label',titles[metricChoice]+'趋势，点击、拖动或方向键查看读数');};
  const networkChange=$('interface')?.onchange;if($('interface'))$('interface').onchange=e=>{if(networkChange)networkChange(e);drawChart();};
  chart.tabIndex=0;chart.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();chartIndex=Math.max(0,Math.min(history.length-1,(chartIndex<0?history.length-1:chartIndex)+(e.key==='ArrowLeft'?-1:1)));drawChart(chartIndex);}});
 }
 const detail=window.showProcessDetail;
 if(detail)window.showProcessDetail=async function(pid){
  stopObservability();const epoch=generation,key=serverKey();await detail(pid);if(epoch!==generation||key!==serverKey()||!$('sheet').open||!$('sheet-content').querySelector('.process-facts'))return;
  const p=processData?.processes.find(p=>p.pid===pid);if(p)attachProcessHistory($('sheet-content'),p);
 };
 window.attachProcessHistory=function(box,p){
  if(!box.isConnected||!$('sheet').open||box.querySelector('.process-history'))return;
  const key=serverKey(),marker=element('div',undefined,'process-history'),select=element('select'),canvas=element('canvas'),readout=element('p','正在积累历史…','footnote'),note=element('p','仅在查看此进程时积累最多 15 分钟历史；CPU 单核 100%。','footnote');select.id='process-history-metric';select.setAttribute('aria-label','进程历史指标');for(const k of['cpu_percent','rss_bytes']){const o=element('option',titles[k]);o.value=k;select.append(o);}canvas.id='process-history-chart';canvas.setAttribute('aria-label','进程历史趋势');canvas.tabIndex=0;marker.append(element('h3','进程历史'),select,canvas,readout,note);box.append(marker);
  const s=processSession={box,marker,endpoint:key,page,generation,rows:[],index:-1,stopped:false};const render=()=>draw(canvas,s.rows,select.value,'',readout,s.index);select.onchange=()=>{s.index=-1;render();};canvas.onpointerdown=e=>{const rect=canvas.getBoundingClientRect();s.index=Math.round(Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width))*(s.rows.length-1));render();};canvas.onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();s.index=Math.max(0,Math.min(s.rows.length-1,(s.index<0?s.rows.length-1:s.index)+(e.key==='ArrowLeft'?-1:1)));render();}};
  async function poll(){if(!usable(s))return;try{const data=await api('/api/processes/history',{pid:p.pid,start:p.start});if(!usable(s))return;s.rows=data.points;render();if(data.ended){note.textContent='进程已退出，保留已采集历史';s.stopped=true;}}catch(e){if(usable(s)){note.textContent=e.message+'；历史已保留';if(/409|404|变化|退出|不存在/.test(e.message))s.stopped=true;}}finally{if(usable(s))s.timer=setTimeout(poll,3000);}}
  poll();
 };
 window.alertItems=function(box,events,empty){if(!events.length){box.append(element('p',empty,'intro'));return;}for(const e of events){const card=element('div',undefined,'card alert-item');card.append(element('b',e.title),element('p',e.message),element('small',new Date(e.time*1000).toLocaleString('zh-CN')+' · '+(e.state==='active'?'异常':e.recovered===false?'监控已取消':'已恢复')));box.append(card);}};
 if(typeof toolPages!=='undefined'&&toolPages.alerts){const base=toolPages.alerts;toolPages.alerts=async box=>{
  const epoch=generation,key=serverKey();await base(box);if(!box.isConnected||epoch!==generation||key!==serverKey())return;
  const data=await api('/api/alerts');if(!box.isConnected||epoch!==generation||key!==serverKey())return;
  const summary=box.querySelector('.card .intro');if(summary)summary.textContent='连续 '+(data.rules.debounce_samples??3)+' 次异常才触发，连续 '+(data.rules.recovery_samples??2)+' 次正常后恢复。';
  const card=element('div',undefined,'card'),bad=element('input'),good=element('input'),save=element('button','保存连续采样规则','primary'),note=element('p','','field-error');card.append(element('h2','持续异常与恢复'));for(const [input,id,title,value]of[[bad,'alert-debounce','触发前连续异常次数',data.rules.debounce_samples??3],[good,'alert-recovery','恢复前连续正常次数',data.rules.recovery_samples??2]]){input.id=id;input.type='number';input.min=1;input.max=20;input.value=value;const label=element('label',title,'field-label');label.htmlFor=id;card.append(label,input);}const behaviorSupported=Number.isInteger(data.rules.debounce_samples)&&Number.isInteger(data.rules.recovery_samples);if(!behaviorSupported){bad.disabled=good.disabled=save.disabled=true;note.textContent='此后端尚不支持连续采样规则，请升级后端；阈值和本机提醒设置仍可使用。';}card.append(element('p','指标每 15 秒检查，服务每 60 秒检查。短暂恢复不会产生重复提醒；无法读取数据不表示恢复。','footnote'),note,save);save.onclick=async()=>{save.disabled=true;try{const latestRules=(await api('/api/alerts')).rules;await api('/api/alerts/rules',{...latestRules,debounce_samples:Number(bad.value),recovery_samples:Number(good.value)});toast('连续采样规则已保存');}catch(e){note.textContent=e.message;}finally{save.disabled=false;}};box.append(card);
  const prefs=element('div',undefined,'card');prefs.append(element('h2','这台手机的提醒设置'));box.append(prefs);
  try{const settings=await local('notificationSettings');if(!box.isConnected||epoch!==generation||key!==serverKey())return;if(settings.available===false||settings.schema!==1)throw Error('当前客户端不支持提醒偏好，请升级 App');const fields={};for(const [name,title]of[['enabled','允许异常通知'],['recovery','异常恢复时通知']]){const label=element('label',undefined,'check-row'),input=element('input');input.id='notify-'+name;input.type='checkbox';input.checked=!!settings[name];fields[name]=input;label.append(input,element('span',title));prefs.append(label);}for(const [name,title]of[['quiet_start','安静时段开始'],['quiet_end','安静时段结束']]){const label=element('label',title,'field-label'),input=element('input');input.id='notify-'+name;input.type='time';input.value=settings[name]||'00:00';fields[name]=input;label.htmlFor=input.id;prefs.append(label,input);}const button=element('button','保存本机提醒设置','primary'),error=element('p','','field-error');prefs.append(element('p','按手机本地时间，可跨午夜；开始和结束相同表示关闭安静时段。安静时段或关闭通知期间的事件仍记录在服务器，不会稍后补发。设置应用于这台手机。','footnote'),error,button);button.onclick=async()=>{button.disabled=true;try{await local('notificationSettings',{schema:1,enabled:fields.enabled.checked,recovery:fields.recovery.checked,quiet_start:fields.quiet_start.value,quiet_end:fields.quiet_end.value});toast('本机提醒设置已保存');}catch(e){error.textContent=e.message;}finally{button.disabled=false;}};}catch(e){prefs.append(element('p',e.message,'footnote'));}
 };}
})();
