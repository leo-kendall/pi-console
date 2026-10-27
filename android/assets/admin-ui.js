// SPDX-License-Identifier: Apache-2.0
'use strict';
const deviceRoles={admin:'管理员',operator:'操作员',viewer:'只读'};
toolInfo.push(['devices','配对设备','命名手机、查看权限与撤销设备','link'],['grants','控制授权','设置服务和容器的操作权限','sliders']);
function adminContext(){return $('server-summary').dataset.endpoint||'';}
function adminCurrent(box,context){return box.isConnected&&context===adminContext();}
function adminError(box,error){if(box.isConnected)box.append(element('p',error.message,'field-error'));}
function adminConfirm(title,description,perform){
 const context=adminContext(),box=sheet(title),note=element('p','','field-error'),button=element('button','确认执行','primary');
 box.append(element('p',description),note,button);
 button.onclick=async()=>{if(button.disabled)return;button.disabled=true;try{if(!adminCurrent(box,context))throw Error('服务器已变化，请重新确认');const close=await perform();if(close!==false&&adminCurrent(box,context)){$('sheet').close();toast('已保存');}}catch(error){if(adminCurrent(box,context)){note.textContent=error.message;button.disabled=false;}}};
}
function renameDevice(device){
 const context=adminContext(),box=sheet('设备名称'),input=element('input'),note=element('p','','field-error'),save=element('button','保存名称','primary');
 input.value=device.name;input.maxLength=64;input.setAttribute('aria-label','设备名称');box.append(input,note,save);
 save.onclick=async()=>{if(save.disabled)return;save.disabled=true;try{const name=input.value.trim();if(!name||/[\x00-\x1f\x7f]/.test(name))throw Error('请输入 1 至 64 个可见字符');if(!adminCurrent(box,context))throw Error('服务器已变化');await api('/api/devices/rename',{device:device.id,name});if(adminCurrent(box,context)){$('sheet').close();openTool('devices');}}catch(error){if(adminCurrent(box,context)){note.textContent=error.message;save.disabled=false;}}};
}
toolPages.devices=async box=>{
 const context=adminContext(),session=await api('/api/session');if(!adminCurrent(box,context))return;
 const isAdmin=session.role==='admin',data=isAdmin?await api('/api/devices'):{devices:[{...session,current:true}]};if(!adminCurrent(box,context))return;
 box.replaceChildren(element('p','当前权限：'+(deviceRoles[session.role]||'未知')+'。设备身份仅用于此服务器，撤销后需要重新配对。','intro'));
 for(const device of data.devices){
  const card=element('div',undefined,'card admin-card');card.append(element('h3',device.name+(device.current?' · 当前设备':'')),element('p',deviceRoles[device.role]||'未知权限'),element('small',device.last_seen?'最近访问 '+new Date(device.last_seen*1000).toLocaleString('zh-CN'):'尚无访问记录'));
  const rename=element('button','修改名称','text-button');rename.dataset.deviceRename=device.id;rename.onclick=()=>renameDevice(device);card.append(rename);
  if(isAdmin){
   const role=element('select');role.setAttribute('aria-label',device.name+'的权限');for(const [value,label]of Object.entries(deviceRoles)){const option=element('option',label);option.value=value;role.append(option);}role.value=device.role;
   const change=element('button','修改权限','text-button');change.onclick=()=>adminConfirm('修改设备权限？',device.name+' 将改为'+deviceRoles[role.value]+'。只读设备无法执行写操作。',async()=>{await api('/api/devices/role',{device:device.id,role:role.value});openTool('devices');});card.append(role,change);
   if(!device.current){const revoke=element('button','撤销设备','text-button danger-text');revoke.dataset.deviceRevoke=device.id;revoke.onclick=()=>adminConfirm('撤销 '+device.name+'？','此设备将立即失去连接权限，正在运行的桌面也会关闭。',async()=>{await api('/api/devices/revoke',{device:device.id});openTool('devices');});card.append(revoke);}
  }box.append(card);
 }
 if(isAdmin){
  const card=element('div',undefined,'card'),role=element('select');role.setAttribute('aria-label','新设备权限');for(const [value,label]of Object.entries(deviceRoles)){const option=element('option',label);option.value=value;role.append(option);}role.value='viewer';
  const create=element('button','生成一次性配对码','primary');card.append(element('h3','添加设备'),element('p','在目标设备填写当前服务器地址，再输入配对码。新码会替换上一枚未使用的码。'),role,create);create.onclick=()=>adminConfirm('生成配对码？','新设备将获得'+deviceRoles[role.value]+'权限，配对码 10 分钟内只能使用一次。',async()=>{const d=await api('/api/devices/pair-code',{role:role.value});if(context!==adminContext())return;const target=sheet('新设备配对码');target.append(element('code',d.code),element('p','有效期 10 分钟，请仅提供给你信任的人。'));return false;});box.append(card);
 }else box.append(element('p','只有管理员可以查看其他设备、分配权限和生成新设备配对码。','footnote'));
};
toolPages.grants=async box=>{
 const context=adminContext(),[session,data,inventory]=await Promise.all([api('/api/session'),api('/api/grants'),api('/api/resources')]);if(!adminCurrent(box,context))return;
 if(session.role!=='admin')throw Error('需要管理员权限');
 box.replaceChildren(element('p','逐项选择允许的动作并确认。授权保存在服务器，系统基础服务继续只读；容器被替换后需要重新授权。','intro'));
 if(!data.system_helper_ready)box.append(element('p','系统服务控制需要在对应后端目录安装或更新执行器：','footnote'),element('code','sudo /usr/bin/python3 -I -B system-control/manage.py install'));
 const search=element('input');search.type='search';search.placeholder='搜索服务或容器';search.setAttribute('aria-label','搜索授权对象');const list=element('div');box.append(search,list);
 const render=()=>{list.replaceChildren();for(const row of inventory.resources.filter(r=>(r.name+' '+r.target).toLowerCase().includes(search.value.trim().toLowerCase()))){const card=element('div',undefined,'card admin-card'),grant=data.grants.find(g=>g.resource===row.id),edit=element('button','设置控制权限','text-button');card.append(element('h3',row.name),element('code',row.target),element('p',grant?.rights.length?'已授权：'+grant.rights.map(a=>({start:'启动',stop:'停止',restart:'重启',logs:'日志'}[a])).join('、'):'尚未添加手机端授权'));edit.dataset.editGrant=row.id;edit.onclick=()=>editGrant(row,grant);card.append(edit);list.append(card);}};search.oninput=render;render();
};
function editGrant(row,grant){
 const context=adminContext(),box=sheet('控制权限 · '+row.name),checks=[];box.append(element('code',row.target),element('p','选择允许的动作。停止或重启会中断此应用的任务与连接；系统基础服务的修改会被拒绝。'));
 for(const [value,label]of [['start','启动'],['stop','停止'],['restart','重启'],['logs','查看日志']]){const wrapper=element('label',undefined,'check-row'),input=element('input');input.type='checkbox';input.value=value;input.checked=!!grant?.rights.includes(value);wrapper.append(input,element('span',label));box.append(wrapper);checks.push(input);}
 const note=element('p','','field-error'),save=element('button','确认保存权限','primary'),remove=element('button','撤销此对象全部权限','text-button danger-text');box.append(note,save,remove);
 const submit=async revoke=>{if(save.disabled)return;save.disabled=remove.disabled=true;try{if(!adminCurrent(box,context))throw Error('服务器已变化，请重新确认');await api(revoke?'/api/grants/remove':'/api/grants/set',revoke?{resource:row.id}:{resource:row.id,rights:checks.filter(c=>c.checked).map(c=>c.value),identity:row.identity||''});if(adminCurrent(box,context)){$('sheet').close();openTool('grants');}}catch(error){if(adminCurrent(box,context)){note.textContent=error.message;save.disabled=remove.disabled=false;}}};save.onclick=()=>submit(false);remove.onclick=()=>submit(true);
}
