// SPDX-License-Identifier: Apache-2.0
'use strict';
(()=>{
 let connection={url:null,paired:false},probeSequence=0,probeRun=0,checkSequence=0,probing=false,checking=false,verified=false;
 function render(){
  const stage=connection.paired?'verify':connection.url?'pair':'address',index=['address','pair','verify'].indexOf(stage);
  $('setup-guide').dataset.stage=stage;
  $('setup-progress').textContent=connection.paired?'已配对':'第 '+(index+1)+' 步 / 共 3 步';
  $('setup-title').textContent={address:'连接你的服务器',pair:'授权这台手机',verify:'连接与功能检查'}[stage];
  $('setup-description').textContent={address:'填写手机可以访问的 HTTPS API 地址，再检测连接。',pair:'地址已保存。在对应服务器生成配对码，授权这台手机。',verify:'配对已保留。可以重新检测地址，或检查服务器上的可选功能。'}[stage];
  document.querySelectorAll('[data-setup-stage]').forEach((node,i)=>{node.classList.toggle('current',i===index);node.classList.toggle('complete',i<index);if(i===index)node.setAttribute('aria-current','step');else node.removeAttribute('aria-current');});
  $('pair-entry').hidden=connection.paired;
  const draftChanged=$('server-url').value.trim()!==(connection.url||'');
  $('pair').disabled=pairingInProgress||connection.paired||!connection.url||draftChanged;
  $('setup-draft-notice').hidden=!draftChanged;
  $('setup-check-target').textContent='检查已保存的服务器：'+(connection.url||'尚未保存');
  $('pair-copy').textContent=connection.paired?'这台手机已配对。更换服务器前，请先撤销当前配对。':'配对只授权这台手机，不会自动开放服务器的所有控制权限。';
  $('setup-verification').hidden=!connection.paired;
  $('save-server').disabled=probing||connection.paired;
  $('save-server').textContent=connection.paired?'当前服务器已配对':'保存并继续';
  $('probe-server').disabled=probing||!$('server-url').value.trim();
  $('probe-server').textContent=probing?'正在检测…':'检测这个地址';
  $('setup-check').disabled=checking||!connection.paired;
  $('setup-check').textContent=checking?'正在检查…':'检查连接与功能';
  $('setup-finish').disabled=checking||!verified||!connection.paired;
 }
 function clearProbe(){probeSequence++;$('connection-result').hidden=true;$('connection-result').replaceChildren();delete $('connection-result').dataset.code;}
 function clearChecks(){checkSequence++;checking=false;verified=false;$('setup-checks').replaceChildren();$('setup-check-error').textContent='';}
 window.setupConnectionChanged=next=>{
  if(connection.url!==next.url||connection.paired!==next.paired){clearProbe();clearChecks();}
  connection={url:next.url||'',paired:!!next.paired};render();
 };
 $('server-url').addEventListener('input',()=>{clearProbe();render();});
 $('probe-server').onclick=async()=>{
  if(probing)return;
  const draft=$('server-url').value,sequence=++probeSequence,run=++probeRun;probing=true;render();$('connection-result').hidden=true;
  try{
   const result=await local('probeServer',draft.trim());
   if(sequence!==probeSequence||draft!==$('server-url').value)return;
   const box=$('connection-result');box.dataset.code=result.code;box.classList.toggle('passed',result.ok===true);
   box.replaceChildren(element('b',result.title),element('p',result.detail),element('small',(result.http_status?'HTTP '+result.http_status+' · ':'')+number(result.elapsed_ms)+' ms · 本次只读检测'));
   box.hidden=false;
  }catch(error){if(sequence===probeSequence){const box=$('connection-result');box.dataset.code='failed';box.classList.remove('passed');box.replaceChildren(element('b','检测未完成'),element('p',error.message));box.hidden=false;}}
  finally{if(run===probeRun){probing=false;render();}}
 };
 function checkRow(title,state,detail){
  const row=element('div',undefined,'setup-check-row'),heading=element('div',undefined,'row');
  heading.append(element('b',title),element('span',({ok:'已验证',configured:'已配置',optional:'可选',attention:'待检查'})[state]||'待检查','badge'));
  row.dataset.state=state;row.append(heading,element('p',detail));return row;
 }
 $('setup-check').onclick=async()=>{
  if(checking||!connection.paired)return;
  const sequence=++checkSequence;checking=true;verified=false;$('setup-check-error').textContent='';$('setup-checks').replaceChildren();render();
  try{
   const status=await api('/api/status');
   if(sequence!==checkSequence)return;
   if(!status||typeof status.metrics!=='object'||status.metrics===null)throw Error('后端状态格式不兼容，请核对 App 与后端版本');
   $('connection').textContent=(status.name||'服务器')+' · 已连接';$('dot').classList.add('online');$('time').textContent='刚刚检查';
   $('setup-checks').append(checkRow('配对与状态读取','ok','已通过当前配对读取服务器状态。'));
   let report;
   try{report=await api('/api/setup');}
   catch(error){if(!error.message.includes('（404）'))throw error;report={checks:[{title:'可选功能配置',state:'optional',detail:'旧版后端未提供配置检查；基础连接已验证。升级后端后可查看详细配置。'}]};}
   if(sequence!==checkSequence)return;
   if(!Array.isArray(report?.checks)||report.checks.length>16)throw Error('功能检测结果不完整，请核对后端版本');
   for(const row of report.checks){if(typeof row.title!=='string'||typeof row.detail!=='string')throw Error('功能检测结果不完整，请重试');$('setup-checks').append(checkRow(row.title,row.state,row.detail));}
   verified=true;
  }catch(error){if(sequence===checkSequence){verified=false;$('setup-check-error').textContent=error.message;}}
  finally{if(sequence===checkSequence){checking=false;render();}}
 };
 $('setup-finish').onclick=()=>{if(verified&&connection.paired&&!checking)navigate('overview');};
 window.pauseSetup=()=>{clearProbe();probeRun++;probing=false;clearChecks();render();};
 window.renderSetup=render;
 // The initial native settings request can complete before this script is loaded.
 if($('server-summary').dataset.endpoint!==undefined)setupConnectionChanged({url:$('server-summary').dataset.endpoint,paired});else render();
})();
