'use strict';
let resourceLoading=false,resourceTimer=null,resourceRows=[],resourceFilter='all',resourceRenderKey='';
let resourceContext='';
window.stopResourcePolling=()=>{clearTimeout(resourceTimer);resourceTimer=null;};
window.resetResourceCache=()=>{stopResourcePolling();resourceRows=[];resourceRenderKey='';$('resources').replaceChildren(element('div','正在等待当前服务器的服务列表','card empty'));$('resource-status').textContent='等待检查';};
window.resourceConnectionChanged=(url,isPaired)=>{const key=JSON.stringify([url,isPaired]);if(key!==resourceContext){resourceContext=key;resetResourceCache();}};
function resourcesVisible(){return active&&paired&&page==='manage'&&manageTab==='services';}
function renderResources(){
 const query=$('resource-search').value.trim().toLowerCase();
 const rows=resourceRows.filter(r=>(resourceFilter==='all'||r.kind===resourceFilter)&&(!query||[r.name,r.target,r.description,r.image].join(' ').toLowerCase().includes(query)));
 const key=JSON.stringify([rows,query,resourceFilter,actionJournal.all()]);if(key===resourceRenderKey)return;resourceRenderKey=key;
 $('resources').replaceChildren();
 if(!rows.length)$('resources').append(element('div',resourceRows.length?'没有匹配的服务或容器':'尚未授权服务或容器；自动扫描也未发现可显示的对象。请检查 systemd、Docker 和读取权限。','card empty'));
 for(const r of rows){
  const card=element('div',undefined,'card resource-card');card.append(element('div',{user:'用户服务',system:'系统服务',container:'应用容器'}[r.kind]||'服务','resource-kind'));
  const row=element('div',undefined,'row resource-heading');row.append(element('h3',r.name),element('span',stateLabel(r.state),'badge'));card.append(row);
  if(r.target&&r.target!==r.name)card.append(element('code',r.target));
  if(r.description)card.append(element('small',r.description));
  card.append(element('p',r.impact));
  const actions=element('div',undefined,'actions');
  for(const [action,label] of [['start','启动'],['stop','停止'],['restart','重启'],['logs','日志']]){
   const button=element('button',label);button.disabled=action==='logs'?!r.logs:!r.control;
   button.onclick=()=>action==='logs'?showLogs(r):confirmAction(r,action,label);actions.append(button);
  }
  card.append(actions);
  if(r.can_authorize_end&&!r.control){const end=element('button','授权结束','text-button danger-text');end.dataset.authorizeEnd=r.id;end.onclick=()=>authorizeResourceEnd(r,end);card.append(end);}
  if(r.configured===false)card.append(element('p',r.can_authorize_end?'可在 App 内确认后结束本次运行，无需修改控制清单。':r.end_reason||'后端尚未提供单次授权，请更新后端。','footnote'));
  else if(!r.control&&r.kind==='system')card.append(element('p','需要在服务器安装本项目的系统服务权限助手','footnote'));
  if(actionJournal.get(r.id)){const recover=element('button','查看待核实操作','text-button');recover.onclick=()=>recoverAction(r);card.append(recover);}
  $('resources').append(card);
 }
}
async function authorizeResourceEnd(r,button){
 if(actionJournal.get(r.id)){recoverAction(r);return;}
 const context=resourceContext;button.disabled=true;
 try{
  const prepared=await api('/api/resources/prepare-end',{resource:r.id});if(context!==resourceContext)return;
  if(!prepared.ready){const box=sheet('当前无法结束');box.append(element('p',prepared.reason||'请刷新后重试'));if(prepared.requires_admin)box.append(element('p','在服务器终端，使用运行后端的 Linux 用户，先进入对应的后端项目目录，再执行：'),element('code','sudo /usr/bin/python3 -I -B process-control/manage.py install'));return;}
  const box=sheet('授权结束 '+prepared.name+'？');box.append(element('code',prepared.target),element('p',prepared.description));
  const note=element('p','','field-error'),confirm=element('button','确认授权并结束','primary');box.append(note,confirm);
  confirm.onclick=async()=>{
   if(context!==resourceContext){note.textContent='服务器或配对已变化，请重新确认';confirm.disabled=true;return;}
   confirm.disabled=true;const request=crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random().toString(36).slice(2);
   try{
    const action=prepared.mode==='process-terminate'?'terminate':'stop';
    const record=actionJournal.begin(r.id,action,request),op=await api('/api/resources/end',{ticket:prepared.ticket,request});
    actionJournal.attach(r.id,op);record.id=op.id;
    if(await trackAction(r,record,note)){if(box.contains(confirm))$('sheet').close();await loadResources();}
   }catch(error){note.textContent=error.message+'；请核实原操作，不会自动重试。';}
  };
 }catch(error){toast(error.message);}finally{button.disabled=false;}
}
async function loadResources(){
 stopResourcePolling();if(resourceLoading||!resourcesVisible())return;
 resourceLoading=true;$('resource-refresh').disabled=true;
 const context=resourceContext;
 try{
  const data=await api('/api/resources');if(!resourcesVisible()||context!==resourceContext)return;
  resourceRows=data.resources;renderResources();
  const when=new Date((data.sampled_at||Date.now()/1000)*1000).toLocaleTimeString('zh-CN',{hour12:false});
  const discovery=data.discovery;
  $('resource-status').textContent=discovery?.supported?'发现 '+resourceRows.length+' 项 · 约每 10 秒检查 · 更新于 '+when+(discovery.partial?' · 部分来源无法读取或结果不完整':''):'后端尚未提供自动发现，请更新后端。';
  if(discovery?.partial){const missing=(discovery.sources||[]).filter(s=>!s.available).map(s=>({user:'用户服务',system:'系统服务',container:'Docker 容器'}[s.kind]));$('resource-status').textContent+=missing.length?'（'+[...new Set(missing)].join('、')+'）':'';}
 }catch(e){if(resourcesVisible()&&context===resourceContext)$('resource-status').textContent='刷新失败，保留当前服务器上次列表：'+e.message;}
 finally{resourceLoading=false;$('resource-refresh').disabled=false;if(resourcesVisible())resourceTimer=setTimeout(loadResources,10000);}
}
$('resource-refresh').onclick=loadResources;
$('resource-search').addEventListener('input',renderResources);
document.querySelectorAll('[data-resource-kind]').forEach(button=>button.onclick=()=>{resourceFilter=button.dataset.resourceKind;document.querySelectorAll('[data-resource-kind]').forEach(b=>b.classList.toggle('selected',b===button));renderResources();});
