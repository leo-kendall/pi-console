// SPDX-License-Identifier: Apache-2.0
'use strict';
(()=>{
 const box=element('div',undefined,'card');box.id='app-updates';const title=element('h2','应用更新'),version=element('p','正在读取当前版本…');version.id='update-version';
 const channel=element('select');channel.id='update-channel';channel.setAttribute('aria-label','更新通道');for(const [value,label]of[['stable','正式版'],['prerelease','含测试版']]){const option=element('option',label);option.value=value;channel.append(option);}
 const check=element('button','检查官方更新','text-button');check.id='update-check';const notes=element('pre');notes.id='update-notes';const message=element('p','','footnote');message.id='update-message';message.setAttribute('role','status');
 const download=element('button','下载并校验','primary');download.id='update-download';download.hidden=true;const install=element('button','打开 Android 安装确认','primary');install.id='update-install';install.hidden=true;
 box.append(title,version,channel,check,notes,message,download,install,element('p','从 leo-kendall/pi-console 的 GitHub Releases 获取。只在点击后检查；下载在后台继续。安装前校验 SHA256、包名及签名兼容性，最终由 Android 确认。更新不会改变服务器配对。','footnote'));$('settings').append(box);
 let candidate=null,poll=null,checking=false;
 window.loadUpdateState=async()=>{try{const s=await local('updateState');if(!candidate)version.textContent='当前版本 '+s.current;message.textContent=s.message;install.hidden=s.state!=='ready';download.disabled=s.state==='downloading';clearTimeout(poll);if(s.state==='downloading'&&active&&page==='settings')poll=setTimeout(loadUpdateState,1500);}catch(e){message.textContent=e.message;}};
 check.onclick=async()=>{if(checking)return;checking=true;check.disabled=true;channel.disabled=true;download.hidden=true;notes.textContent='';message.textContent='正在检查官方发布…';try{candidate=await local('checkUpdate',channel.value);version.textContent='当前 '+candidate.current+(candidate.available?' → '+candidate.version:' · 已是所选通道最新版本');notes.textContent=candidate.notes||'';download.hidden=!candidate.downloadable;message.textContent=candidate.blocked||'检查完成';}catch(e){message.textContent=e.message;}finally{checking=false;check.disabled=false;channel.disabled=false;}};
 channel.onchange=()=>{candidate=null;download.hidden=true;notes.textContent='';message.textContent='通道已更改，请重新检查';};
 download.onclick=async()=>{if(!candidate?.downloadable)return;download.disabled=true;try{await local('downloadUpdate',candidate.version);message.textContent='后台下载已开始';poll=setTimeout(loadUpdateState,500);}catch(e){message.textContent=e.message;download.disabled=false;}};
 install.onclick=async()=>{install.disabled=true;try{await local('installUpdate');message.textContent='请在 Android 安装界面确认';}catch(e){message.textContent=e.message;}finally{install.disabled=false;}};
 document.querySelector('[data-page="settings"]').addEventListener('click',loadUpdateState);loadUpdateState();
})();
