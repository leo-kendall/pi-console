'use strict';
let manageTab='services',processTimer=null,processLoading=false,processData=null,processFilter='closable',processSort='memory';
window.stopProcessPolling=()=>{clearTimeout(processTimer);};
window.showManage=function(){
 const show=manageTab==='processes';$('services-pane').hidden=manageTab!=='services';$('processes-pane').hidden=!show;$('tools-pane').hidden=manageTab!=='tools';if(window.pauseTools)pauseTools();
 document.querySelectorAll('[data-manage-tab]').forEach(b=>{const selected=b.dataset.manageTab===manageTab;b.classList.toggle('selected',selected);b.setAttribute('aria-selected',String(selected));});
 stopProcessPolling();if(window.stopResourcePolling)stopResourcePolling();if(show)loadProcesses();else if(manageTab==='tools')renderTools();else loadResources();
};
function openProcesses(){manageTab='processes';if(page!=='manage')navigate('manage');else showManage();}
document.querySelectorAll('[data-manage-tab]').forEach(b=>b.onclick=()=>{manageTab=b.dataset.manageTab;showManage();});
function processDuration(seconds){let n=Math.max(0,Math.floor(seconds||0));return n>=86400?Math.floor(n/86400)+' 天 '+Math.floor(n%86400/3600)+' 小时':n>=3600?Math.floor(n/3600)+' 小时 '+Math.floor(n%3600/60)+' 分钟':Math.floor(n/60)+' 分钟';}
function processState(state){return {R:'正在运行',S:'睡眠等待',D:'等待输入输出',T:'已暂停',t:'调试暂停',Z:'等待回收',I:'空闲',X:'已退出',x:'已退出',K:'等待唤醒',P:'已停放'}[state]||'状态未知';}
function processResource(p){return {id:'process-'+p.pid+'-'+p.start,name:p.name+' · PID '+p.pid};}
function renderProcesses(){
 if(!processData)return;
 const query=$('process-search').value.trim().toLowerCase();let rows=processData.processes.filter(p=>(processFilter==='all'||(processFilter==='readonly'?!p.can_close:p.can_close))&&(!query||[p.name,p.pid,p.owner,p.exe].join(' ').toLowerCase().includes(query)));
 rows.sort((a,b)=>processSort==='cpu'?(b.cpu_percent??-1)-(a.cpu_percent??-1)||b.rss_bytes-a.rss_bytes:b.rss_bytes-a.rss_bytes);
 $('process-count').textContent=processData.count;$('process-closable').textContent=processData.closable+' 个可结束进程';$('process-available').textContent=size(processData.memory_available);
 $('process-updated').textContent='更新于 '+new Date(processData.sampled_at*1000).toLocaleTimeString('zh-CN',{hour12:false});
 $('process-list').replaceChildren();for(const record of Object.values(actionJournal.all()).filter(r=>r.resource.startsWith('process-'))){const pending=element('button','核实关闭请求 · '+record.resource,'card pending-process');pending.onclick=()=>recoverProcess({id:record.resource,name:record.resource});$('process-list').append(pending);}
 for(const p of rows){const card=element('div',undefined,'card process-card');const button=element('button',undefined,'process-open');
 const title=element('div',undefined,'row');title.append(element('h3',p.name),element('span',p.can_close?(p.control_available===false?'待授权':'可正常结束'):p.category==='exited'?'已退出':p.category==='system_core'?'系统只读':'暂不可操作','badge'+(p.can_close?'':' protected-badge')));
 const stats=element('div',undefined,'process-stats');stats.append(element('strong',size(p.rss_bytes)),element('span','CPU '+(p.cpu_percent===null?'采样中':number(p.cpu_percent,1)+'%')));
 button.append(title,element('small','PID '+p.pid+' · '+p.owner+' · '+processState(p.state)),stats);
 if(p.can_close&&p.app_rss_bytes>p.rss_bytes)button.append(element('small','同组进程 RSS '+size(p.app_rss_bytes)));
 button.onclick=()=>showProcessDetail(p.pid);card.append(button);
 const r=processResource(p);if(actionJournal.get(r.id)){const recovery=element('button','核实上次关闭请求','text-button');recovery.onclick=()=>recoverProcess(r);card.append(recovery);}
 $('process-list').append(card);}
 if(!rows.length)$('process-list').append(element('div',query?'没有匹配的进程':processFilter==='closable'?'当前没有可结束的应用进程，可切换“全部进程”查看':'暂无进程数据','card empty'));
 $('process-note').textContent=(processData.admin_helper_ready?'管理员进程管理已启用。':'部分应用需要在服务器完成一次管理员授权。')+'每 3 秒刷新 · CPU 以单核 100% 计算。RSS 包含共享页，不能直接视为可释放内存。'+(processData.shown<processData.count?'全部视图展示内存占用最高的 '+processData.shown+' 项及全部可结束进程。':'');
}
async function loadProcesses(){
 if(processLoading)return;processLoading=true;$('process-refresh').disabled=true;$('process-error').textContent='';
 try{processData=await api('/api/processes');if(page==='manage'&&manageTab==='processes')renderProcesses();}
 catch(e){$('process-error').textContent=e.message+'；上次读数已保留';if(!processData)$('process-list').replaceChildren(element('div','配对后可查看进程详情','card empty'));}
 finally{processLoading=false;$('process-refresh').disabled=false;stopProcessPolling();if(active&&page==='manage'&&manageTab==='processes')processTimer=setTimeout(loadProcesses,3000);}
}
$('process-refresh').onclick=loadProcesses;$('process-search').oninput=renderProcesses;
$('process-sort').onchange=()=>{processSort=$('process-sort').value;renderProcesses();};
document.querySelectorAll('[data-process-filter]').forEach(b=>b.onclick=()=>{processFilter=b.dataset.processFilter;document.querySelectorAll('[data-process-filter]').forEach(n=>n.classList.toggle('selected',n===b));renderProcesses();});
async function showProcessDetail(pid){
 const box=sheet('进程详情'),loading=element('p','正在读取最新信息…');box.append(loading);
 try{
  const p=await api('/api/processes/'+pid);if(!box.isConnected||!$('sheet').open||!box.contains(loading))return;box.replaceChildren();$('sheet-title').textContent=p.name;
  const facts=[['进程 ID',String(p.pid)],['所属用户',p.owner],['状态',processState(p.state)],['物理内存（RSS）',size(p.rss_bytes)],['占总内存',number(p.memory_percent,1)+'%'],['CPU 使用率',p.cpu_percent===null?'采样中':number(p.cpu_percent,1)+'%'],['虚拟地址空间',size(p.virtual_bytes)],['运行时间',processDuration(p.elapsed_seconds)],['线程数',String(p.threads)],['父进程 ID',String(p.ppid)]];
  if(p.app_rss_bytes>p.rss_bytes)facts.push(['同组进程 RSS',size(p.app_rss_bytes)]);
  const dl=element('dl',undefined,'process-facts');for(const [label,value]of facts)dl.append(element('dt',label),element('dd',value));box.append(dl,element('p','可执行文件','field-label'),element('code',p.exe||'当前用户无法读取路径'),element('p','进程归属','field-label'),element('code',p.cgroup),element('p',p.reason,'process-policy'));
  const refresh=element('button','刷新进程详情','text-button');refresh.onclick=()=>showProcessDetail(pid);box.append(refresh);if(p.can_close&&p.control_available===false){box.append(element('p','这是可结束的应用进程，并非系统只读；当前后台用户没有执行权限。请在服务器终端完成一次管理员授权，然后刷新详情。','process-policy'),element('code','sudo /usr/bin/python3 -I -B process-control/manage.py install'));}
  else if(p.can_close){const r=processResource(p),button=element('button',actionJournal.get(r.id)?'核实上次关闭请求':'正常结束进程','primary danger-button');box.append(button);button.onclick=()=>actionJournal.get(r.id)?recoverProcess(r):confirmProcess(p);}
  else box.append(element('p','当前不能执行结束操作，具体原因见上方说明。','footnote'));
 }catch(e){loading.textContent=e.message;}
}
async function recoverProcess(r){
 const record=actionJournal.get(r.id);if(!record)return;
 const box=sheet(r.name+' · 核实关闭结果'),note=element('p','查询原操作，不会再次发送关闭请求。'),query=element('button','查询原操作','primary'),clear=element('button','我已检查进程状态，清除此记录','text-button');box.append(note,query,clear);
 query.onclick=async()=>{query.disabled=true;try{if(await trackAction(r,record,note)){if($('sheet-content')===box)$('sheet').close();loadProcesses();}}catch(e){note.textContent=e.message+'；原操作记录已保留。';}finally{query.disabled=false;}};
 clear.onclick=()=>{actionJournal.clear(r.id);$('sheet').close();loadProcesses();};query.click();
}
function confirmProcess(p){
 const r=processResource(p),box=sheet('结束 '+p.name+'？');box.append(element('p','PID '+p.pid+' · '+p.owner+' · 内存 '+size(p.rss_bytes)),element('p','将向此进程发送正常结束请求（SIGTERM）。未保存内容可能丢失；受托管的进程可能被应用或服务重新启动。'));
 if(p.impact)box.append(element('p',p.impact,'process-policy danger-text'));
 const note=element('p','','field-error'),button=element('button','确认结束进程','primary danger-button');box.append(note,button);
 button.onclick=async()=>{button.disabled=true;note.textContent='正在提交，请勿重复操作';const request=crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random().toString(36).slice(2);
  try{const record=actionJournal.begin(r.id,'terminate',request),op=await api('/api/processes/terminate',{pid:p.pid,start:p.start,ticket:p.ticket,request});actionJournal.attach(r.id,op);record.id=op.id;if(await trackAction(r,record,note)){$('sheet').close();loadProcesses();}}
  catch(e){note.textContent=e.message+'；请先刷新核实，不会自动重试。';button.textContent='关闭后核实原操作';}
 };
}
