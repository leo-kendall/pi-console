'use strict';
let desktopClient=null,desktopId=null,desktopGeneration=0,desktopConnecting=false,desktopMouse=null,zoomed=false;
let desktopEdgeProbe=null;
let desktopTrace=null,desktopRenderMode=localStorage.getItem('desktop-render-mode')==='default'?'default':'software';
window.addEventListener('error',()=>desktopTrace?.event('window-error'));
window.addEventListener('unhandledrejection',()=>desktopTrace?.event('decode-error'));
window.stopDesktop=function(){desktopEdgeProbe?.dispose();desktopEdgeProbe=null;local('desktopRendering','default').catch(()=>{});leaveDesktopFullscreen();desktopGeneration++;const sid=desktopId;desktopId=null;if(desktopClient){try{desktopClient.disconnect();}catch(e){}desktopClient=null;}if(sid)api('/api/desktop/close/'+sid,{}).catch(()=>{});$('screen').replaceChildren();$('screen').style.width='';$('screen').style.height='';$('desktop-session').hidden=true;document.querySelector('.desktop-intro').hidden=false;$('desktop-connect').disabled=false;$('desktop-connect').textContent='连接桌面';$('desktop-text').value='';desktopConnecting=false;};
let fullscreenDesktop=false,manualFullscreen=false,fullscreenDismissed=false,deviceLandscape=null,resizeDesktopTimer=null;
function isDesktopLandscape(){return deviceLandscape===null?matchMedia('(orientation: landscape)').matches:deviceLandscape;}
function fitDesktop(){
 if(!desktopClient)return;
 const display=desktopClient.getDisplay(),viewport=$('screen-scroll');viewport.classList.toggle('desktop-zoomed',zoomed);
 if(display.getWidth()){
  const scale=fitScale(viewport.clientWidth,fullscreenDesktop?viewport.clientHeight:Math.min(innerHeight*.6,display.getHeight()),display.getWidth(),display.getHeight(),zoomed);
  display.scale(scale);
  // Use the known scaled bounds. Intrinsic max-content sizing can retain an
  // earlier canvas width in mobile WebView during rotation / display updates.
  $('screen').style.width=(display.getWidth()*scale)+'px';
  $('screen').style.height=(display.getHeight()*scale)+'px';
 }
 if(!zoomed){viewport.scrollLeft=0;viewport.scrollTop=0;}
}
function scheduleDesktopResize(){
 clearTimeout(resizeDesktopTimer);
 if(!desktopClient)return;
 const generation=desktopGeneration;
 resizeDesktopTimer=setTimeout(()=>{if(generation===desktopGeneration)resizeRemoteDesktop();},350);
}
function showDesktopControls(show){document.body.classList.toggle('desktop-controls-open',show);$('desk-controls').setAttribute('aria-expanded',String(show));$('desk-controls').textContent=show?'收起':'控件';}
function setDesktopFullscreen(enabled){
 if(fullscreenDesktop===enabled)return;
 fullscreenDesktop=enabled;document.body.classList.toggle('desktop-fullscreen',enabled);
 if(enabled)zoomed=false;
 $('desk-controls').hidden=!enabled;$('desk-fullscreen').textContent=enabled?'退出全屏':'全屏';
 showDesktopControls(false);local('desktopFullscreen',String(enabled)).catch(()=>{});
 requestAnimationFrame(()=>{fitDesktop();scheduleDesktopResize();});
}
function leaveDesktopFullscreen(){manualFullscreen=false;fullscreenDismissed=false;clearTimeout(resizeDesktopTimer);setDesktopFullscreen(false);$('keyboard-box').hidden=true;}
function syncDesktopLayout(){setDesktopFullscreen(Boolean(desktopClient&&(manualFullscreen||isDesktopLandscape()&&!fullscreenDismissed)));fitDesktop();}
function resizeRemoteDesktop(attempt=0){
 if(!desktopClient||!$('keyboard-box').hidden)return;
 const d=desktopClient.getDisplay();
 // The open handshake already requests the initial size. Width/height of
 // zero mean no remote geometry has arrived, not a rejected resize. Wait
 // for onresize instead of sending five duplicate display updates.
 if(!d.getWidth()||!d.getHeight())return;
 let size;if(fullscreenDesktop&&$('resolution').value==='auto'){const v=$('screen-scroll');if(!v.clientWidth||!v.clientHeight)return;size=desktopSize(v.clientWidth,v.clientHeight,devicePixelRatio);}else{const [width,height]=($('resolution').value==='auto'?'1280,800':$('resolution').value).split(',').map(Number);size={width,height};}
 if(d.getWidth()!==size.width||d.getHeight()!==size.height){
  desktopTrace?.sentSize(size.width,size.height);
  desktopClient.sendSize(size.width,size.height);
  // RDP's display-control channel can become ready after the first frame.
  // Stop once confirmed; never replay a resize across desktop sessions.
  if(attempt<4){const generation=desktopGeneration;clearTimeout(resizeDesktopTimer);resizeDesktopTimer=setTimeout(()=>{if(generation===desktopGeneration)resizeRemoteDesktop(attempt+1);},800*(attempt+1));}
 }
}
window.setDeviceLandscape=function(landscape){if(deviceLandscape!==landscape){deviceLandscape=landscape;manualFullscreen=false;fullscreenDismissed=false;zoomed=false;syncDesktopLayout();scheduleDesktopResize();}};
matchMedia('(orientation: landscape)').addEventListener('change',()=>{if(deviceLandscape!==null)return;manualFullscreen=false;fullscreenDismissed=false;zoomed=false;syncDesktopLayout();scheduleDesktopResize();});
window.exitDesktopFullscreen=function(){if(!fullscreenDesktop)return false;manualFullscreen=false;fullscreenDismissed=true;setDesktopFullscreen(false);return true;};
$('desk-fullscreen').onclick=()=>{if(fullscreenDesktop)exitDesktopFullscreen();else{manualFullscreen=true;fullscreenDismissed=false;syncDesktopLayout();}};
$('desk-controls').onclick=()=>{const show=!document.body.classList.contains('desktop-controls-open');showDesktopControls(show);if(!show){$('desktop-text').blur();$('keyboard-box').hidden=true;}};
$('desktop-connect').onclick=async()=>{if(desktopConnecting)return;if(!paired){toast('请先在设置中输入配对码');navigate('settings');return;}desktopConnecting=true;$('desktop-connect').disabled=true;$('desktop-connect').textContent='正在连接…';const generation=++desktopGeneration;try{
 if(typeof Guacamole==='undefined')throw new Error('桌面组件未加载');
 desktopTrace=new DesktopTrace();desktopTrace.event('render-mode',{mode:desktopRenderMode});
 await local('desktopRendering',desktopRenderMode).catch(()=>{});
 if(generation!==desktopGeneration)return;
 let [width,height]=($('resolution').value==='auto'?'1280,800':$('resolution').value).split(',').map(Number);if($('resolution').value==='auto'&&(isDesktopLandscape()||manualFullscreen)){const size=desktopSize(innerWidth,innerHeight,devicePixelRatio);width=size.width;height=size.height;}const data=await api('/api/desktop/open',{width,height});if(generation!==desktopGeneration){api('/api/desktop/close/'+data.id,{}).catch(()=>{});return;}desktopId=data.id;
 const tunnel=new Guacamole.Tunnel(),parser=new Guacamole.Parser();let writes='',writing=false,flushTimer=null;
 const trace=desktopTrace;
 parser.oninstruction=(opcode,args)=>{trace.received(opcode,args);if(tunnel.oninstruction)tunnel.oninstruction(opcode,args);};
 const fail=message=>{if(generation!==desktopGeneration)return;toast(message);stopDesktop();};
 const flush=async()=>{if(writing||!writes||generation!==desktopGeneration)return;writing=true;const chunk=writes;writes='';try{await api('/api/desktop/write/'+data.id,{data:chunk});}catch(e){fail(e.message);}finally{writing=false;if(writes)flush();}};
 tunnel.sendMessage=(...args)=>{if(generation!==desktopGeneration)return;writes+=args.map(v=>{const s=String(v);return Array.from(s).length+'.'+s;}).join(',')+';';if(writes.length>30000){fail('输入队列已满，请重新连接');return;}clearTimeout(flushTimer);flushTimer=setTimeout(flush,20);};
 tunnel.connect=()=>{tunnel.uuid=data.id;tunnel.setState(Guacamole.Tunnel.State.OPEN);(async()=>{while(generation===desktopGeneration){try{const response=await api('/api/desktop/read/'+data.id);if(generation!==desktopGeneration)break;if(response.data)parser.receive(response.data);}catch(e){fail(e.message);break;}}})();};
 tunnel.disconnect=()=>{clearTimeout(flushTimer);tunnel.setState(Guacamole.Tunnel.State.CLOSED);};
 desktopClient=new Guacamole.Client(tunnel);const client=desktopClient,display=client.getDisplay();$('screen').replaceChildren(display.getElement());$('desktop-session').hidden=false;document.querySelector('.desktop-intro').hidden=true;$('desktop-status').textContent='正在等待服务器桌面…';
 positionDesktopCursor(display);
 const flushDisplay=display.flush;
 display.flush=function(callback,...args){return flushDisplay.call(display,()=>{trace.rendered();if(callback)callback();},...args);};
 display.getElement().addEventListener('contextlost',()=>trace.event('contextlost'),true);
 display.getElement().addEventListener('contextrestored',()=>trace.event('contextrestored'),true);
 display.onresize=()=>{fitDesktop();scheduleDesktopResize();$('desktop-status').textContent='已连接 · '+display.getWidth()+' × '+display.getHeight();};client.onerror=e=>fail('桌面连接中断：'+(e.message||'请重试'));client.onstatechange=state=>{if(state===Guacamole.Client.State.CONNECTED){clearTimeout(resizeDesktopTimer);resizeDesktopTimer=setTimeout(resizeRemoteDesktop,100);}};
 desktopEdgeProbe=new DesktopEdgeProbe(()=>{
  if(document.body.classList.contains('desktop-controls-open')||document.body.classList.contains('desktop-sampling'))return {window:{available:false,reason:'controls-open'}};
  return desktopSample(client);
 });const edgeProbe=desktopEdgeProbe;
 const sendMouse=state=>{client.sendMouseState(state,true);edgeProbe.observe(display.getWidth(),display.getHeight(),display.cursorX,display.cursorY,display.getScale());};
 desktopMouse=new Guacamole.Mouse.Touchpad(display.getElement());desktopMouse.onmousedown=desktopMouse.onmouseup=desktopMouse.onmousemove=sendMouse;
 const mouse=new Guacamole.Mouse(display.getElement());mouse.onmousedown=mouse.onmouseup=mouse.onmousemove=sendMouse;
 client.connect();zoomed=false;syncDesktopLayout();
 }catch(e){toast(e.message);stopDesktop();}finally{desktopConnecting=false;$('desktop-connect').disabled=false;$('desktop-connect').textContent='连接桌面';}};
$('desk-disconnect').onclick=stopDesktop;$('desk-fit').onclick=()=>{zoomed=false;fitDesktop();scheduleDesktopResize();};$('desk-zoom').onclick=()=>{zoomed=!zoomed;fitDesktop();};
function desktopViewportChanged(){desktopTrace?.event('viewport',{width:innerWidth,height:innerHeight});requestAnimationFrame(fitDesktop);if(fullscreenDesktop)scheduleDesktopResize();}
window.addEventListener('resize',desktopViewportChanged);if(window.visualViewport)visualViewport.addEventListener('resize',desktopViewportChanged);
if(window.ResizeObserver)new ResizeObserver(desktopViewportChanged).observe($('screen-scroll'));
$('desk-keyboard').onclick=()=>{$('keyboard-box').hidden=!$('keyboard-box').hidden;if(!$('keyboard-box').hidden){showDesktopControls(true);$('desktop-text').focus();}else{$('desktop-text').blur();scheduleDesktopResize();}requestAnimationFrame(fitDesktop);};
function sendKey(key){if(desktopClient){desktopClient.sendKeyEvent(1,key);desktopClient.sendKeyEvent(0,key);}}
document.querySelectorAll('[data-key]').forEach(b=>b.onclick=()=>sendKey(Number(b.dataset.key)));
$('send-text').onclick=()=>{if(!desktopClient)return;const text=$('desktop-text').value;if(text.length>2000){toast('一次最多发送 2000 个字符');return;}for(const c of text){const cp=c.codePointAt(0);sendKey(cp===10?65293:cp<=255?cp:0x01000000|cp);}$('desktop-text').value='';};
$('desk-right').onclick=()=>{if(!desktopClient)return;let s=new Guacamole.Mouse.State(desktopMouse?.currentState?.x||0,desktopMouse?.currentState?.y||0,false,false,true,false,false);desktopClient.sendMouseState(s,true);s.right=false;desktopClient.sendMouseState(s,true);};
for(const [label,key]of[['↑',65362],['↓',65364],['←',65361],['→',65363],['Super',65515]]){const b=element('button',label);b.setAttribute('aria-label',label+' 键');b.onclick=()=>sendKey(key);document.querySelector('.keys').append(b);}
const ctrl=element('button','Ctrl+C');ctrl.onclick=()=>{if(desktopClient){desktopClient.sendKeyEvent(1,65507);sendKey(99);desktopClient.sendKeyEvent(0,65507);}};document.querySelector('.keys').append(ctrl);

async function desktopSample(client){
 const display=client.getDisplay(),canvas=display.flatten(),ctx=canvas.getContext('2d'),box=$('screen').getBoundingClientRect();
 const sample={remote:[display.getWidth(),display.getHeight()],viewport:[innerWidth,innerHeight],frame:[box.x,box.y,box.width,box.height],scale:display.getScale(),cursor:[display.cursorX,display.cursorY],columns:sampleDesktopColumns(canvas.width,canvas.height,(x,y)=>ctx.getImageData(x,y,1,1).data)};
 try{sample.window=await local('desktopProbe',{cssWidth:innerWidth,cssHeight:innerHeight,x:box.x,y:box.y,width:box.width,height:box.height});}
 catch(e){sample.window={available:false,reason:'native-bridge'};}
 return sample;
}
function showDesktopReport(report){
 const body=sheet('桌面显示诊断');body.append(element('p','鼠标进入边缘或角落时会自动记录显示统计，不打开控件、不主动重绘，也不保存截图、按键或桌面文字。手动检查仍可能让黑块恢复；复制诊断会同时包含最近四次边缘记录。'));
 const mode=element('button',report.mode==='software'?'切换到默认绘制':'切换到软件绘制','primary');
 mode.onclick=async()=>{if(!desktopClient){toast('请先连接桌面');return;}const generation=desktopGeneration,next=desktopRenderMode==='software'?'default':'software';mode.disabled=true;try{await local('desktopRendering',next);if(generation!==desktopGeneration)return;desktopRenderMode=next;localStorage.setItem('desktop-render-mode',next);desktopTrace?.event('render-mode',{mode:next});$('sheet').close();toast(next==='default'?'已切换默认绘制，请观察是否仍会出现黑块':'已切换软件绘制，请观察是否仍会出现黑块');}catch(e){toast(e.message);}finally{mode.disabled=false;}};
 body.append(mode,element('p','切换只影响手机显示，不会重连桌面。默认绘制和软件绘制可在同一次连接中对比。','footnote'));
 const copy=element('button','复制诊断','primary');copy.onclick=()=>local('copyDesktopReport',JSON.stringify(report)).then(()=>toast('诊断已复制，可粘贴到聊天中')).catch(e=>toast(e.message));
 body.append(copy,element('pre',JSON.stringify(report,null,2)));
}
$('desk-inspect').onclick=async()=>{
 if(!desktopClient)return;
 if(zoomed||!$('keyboard-box').hidden){toast('请先点适应并收起键盘，再检查画面');return;}
 const client=desktopClient,generation=desktopGeneration,button=$('desk-inspect');button.disabled=true;
 try{
  document.body.classList.add('desktop-sampling');
  await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  if(generation!==desktopGeneration)return;
  desktopTrace.event('inspect');const before=await desktopSample(client);
  if(generation!==desktopGeneration)return;
  await local('desktopRepaint').catch(()=>{});desktopTrace.event('repaint');
  await new Promise(resolve=>setTimeout(resolve,220));
  if(generation!==desktopGeneration)return;
  const after=await desktopSample(client);
  if(generation!==desktopGeneration)return;
  const report={version:'0.5.0-beta.2',build:21,mode:desktopRenderMode,cursorPositioning:'layout',sampling:{controlsHidden:true,mayTriggerRepaint:true,automaticEdgeCapture:true},edges:desktopEdgeProbe?.snapshot()||[],before,after,trace:desktopTrace.snapshot()};
  try{localStorage.setItem('desktop-last-report',JSON.stringify(report));}catch(e){}
  showDesktopReport(report);
 }catch(e){toast('画面仍在调整，请稍后再检查');}finally{document.body.classList.remove('desktop-sampling');button.disabled=false;}
};
