'use strict';
let desktopClient=null,desktopId=null,desktopGeneration=0,desktopConnecting=false,desktopMouse=null,zoomed=false;
let desktopEdgeProbe=null;
let desktopTrace=null,desktopRenderMode=localStorage.getItem('desktop-render-mode')==='software'?'software':'default';
let desktopScaling=null,desktopPresentation=localStorage.getItem('desktop-presentation')==='transform'?'transform':'layout';
let desktopKeyboard=null,desktopHeld=new Map(),desktopRemoteClipboard='',desktopClipboardAvailable=false,desktopNativeMouse=null,desktopBrowserMouse=null;
let desktopInputRemote=true,desktopShortcutHeld=false;
const DESKTOP_CLIPBOARD_LIMIT=16384;
function setDesktopInputTarget(remote){
 if(!desktopClient)return;
 releaseDesktopInput();desktopInputRemote=Boolean(remote);
 const button=$('desk-input-target');button.textContent=desktopInputRemote?'键鼠：远程':'键鼠：手机';button.setAttribute('aria-pressed',String(desktopInputRemote));
 if(desktopKeyboard){desktopKeyboard.onkeydown=desktopInputRemote?desktopBrowserKeyDown:null;desktopKeyboard.onkeyup=desktopInputRemote?desktopBrowserKeyUp:null;}
 setNativeDesktopInput(true);
 if(desktopInputRemote&&!desktopEditorFocused())desktopClient.getDisplay().getElement().focus({preventScroll:true});
 else if(!desktopInputRemote&&desktopClient.getDisplay().getElement().contains(document.activeElement))(!fullscreenDesktop&&button.getClientRects().length?button:$('desk-controls')).focus({preventScroll:true});
 toast(desktopInputRemote?'键鼠控制远程桌面 · Ctrl+Alt+空格切回手机':'键鼠控制手机 · Ctrl+Alt+空格切回远程');
}
function desktopBrowserKeyDown(key){if(desktopInputRemote)desktopKeyState(key,true,'browser');return !desktopInputRemote;}
function desktopBrowserKeyUp(key){if(desktopInputRemote)desktopKeyState(key,false,'browser');}
// Native Activity handles physical keys first. This also supports the browser
// preview and WebViews that deliver a hardware chord through DOM events.
document.addEventListener('keydown',event=>{
 if(!desktopClient||event.isComposing||!(event.code==='Space'||event.keyCode===32))return;
 if(!desktopShortcutHeld&&!(event.ctrlKey&&event.altKey))return;
 event.preventDefault();event.stopImmediatePropagation();
 if(!desktopShortcutHeld&&!event.repeat)setDesktopInputTarget(!desktopInputRemote);
 desktopShortcutHeld=true;
},true);
document.addEventListener('keyup',event=>{if(desktopShortcutHeld&&(event.code==='Space'||event.keyCode===32)){desktopShortcutHeld=false;event.preventDefault();event.stopImmediatePropagation();}},true);
$('desk-input-target').onclick=()=>setDesktopInputTarget(!desktopInputRemote);
function desktopKeyState(key,down,source){
 if(!desktopClient||!Number.isInteger(key)||key<0||key>0x1ffffff)return;
 let sources=desktopHeld.get(key);
 if(down){if(!sources){sources=new Set();desktopHeld.set(key,sources);}const first=sources.size===0,repeat=sources.has(source);sources.add(source);if(first||repeat&&source!=='sticky')desktopClient.sendKeyEvent(1,key);}
 else if(sources&&sources.delete(source)&&sources.size===0){desktopHeld.delete(key);desktopClient.sendKeyEvent(0,key);}
}
function releaseDesktopInput(){
 desktopKeyboard?.reset();
 desktopMouse?.reset();desktopBrowserMouse?.reset();
 if(desktopClient){for(const key of desktopHeld.keys())desktopClient.sendKeyEvent(0,key);if(desktopNativeMouse){desktopNativeMouse.left=desktopNativeMouse.middle=desktopNativeMouse.right=desktopNativeMouse.up=desktopNativeMouse.down=false;desktopClient.sendMouseState(desktopNativeMouse,false);}}
 desktopHeld.clear();desktopNativeMouse=null;
 document.querySelectorAll('[data-modifier]').forEach(b=>b.setAttribute('aria-pressed','false'));
}
function desktopEditorFocused(){const e=document.activeElement;return Boolean(e&&(e.matches('input,textarea,select,[contenteditable=true]')))||Boolean($('sheet')?.open);}
function setNativeDesktopInput(enabled){local('desktopInput',enabled&&desktopClient&&desktopInputRemote&&!desktopEditorFocused()?desktopId:'').catch(()=>{});updateNativeDesktopRegion();}
function updateNativeDesktopRegion(){
 const b=$('screen').getBoundingClientRect(),allowed=desktopClient&&desktopInputRemote&&!desktopEditorFocused()&&!document.body.classList.contains('desktop-controls-open'),clamp=v=>Math.max(0,Math.min(1,v));
 const rect=b=>({left:clamp(b.left/innerWidth),top:clamp(b.top/innerHeight),right:clamp(b.right/innerWidth),bottom:clamp(b.bottom/innerHeight)});
 const exclude=['desk-input-target','desk-controls'].map(id=>rect($(id).getBoundingClientRect())).filter(e=>e.right>e.left&&e.bottom>e.top);
 local('desktopInputRegion',allowed?{...rect(b),exclude}:{left:0,top:0,right:0,bottom:0}).catch(()=>{});
}
window.desktopNativeInput=function(event){
 if(!desktopClient||event.session!==desktopId)return;
 if(event.type==='reset'){releaseDesktopInput();return;}
 if(event.type==='toggle-target'){setDesktopInputTarget(!desktopInputRemote);return;}
 if(!desktopInputRemote||desktopEditorFocused())return;
 if(event.type==='key'){desktopKeyState(event.keysym,Boolean(event.down),'native');return;}
 if(event.type!=='mouse'||![event.x,event.y,event.buttons,event.wheel||0,event.horizontal||0].every(Number.isFinite))return;
 const d=desktopClient.getDisplay(),b=$('screen').getBoundingClientRect(),x=event.x*innerWidth-b.left,y=event.y*innerHeight-b.top;
 if(x<0||y<0||x>=b.width||y>=b.height)return;
 const scale=d.getScale();desktopNativeMouse=new Guacamole.Mouse.State(Math.min(d.getWidth()-1,Math.max(0,Math.floor(x/scale))),Math.min(d.getHeight()-1,Math.max(0,Math.floor(y/scale))),Boolean(event.buttons&1),Boolean(event.buttons&4),Boolean(event.buttons&2),false,false);
 desktopClient.sendMouseState(desktopNativeMouse,false);
 const steps=Math.min(8,Math.ceil(Math.abs(event.wheel||0)));
 for(let i=0;i<steps;i++){desktopNativeMouse.up=event.wheel>0;desktopNativeMouse.down=event.wheel<0;desktopClient.sendMouseState(desktopNativeMouse,false);desktopNativeMouse.up=desktopNativeMouse.down=false;desktopClient.sendMouseState(desktopNativeMouse,false);}
 // Guacamole's public Mouse.State has vertical wheel buttons only. Horizontal
 // hardware wheels use Shift+wheel, preserving an already-held Shift key.
 const horizontal=Math.min(8,Math.ceil(Math.abs(event.horizontal||0)));
 if(horizontal){desktopKeyState(65505,true,'wheel');for(let i=0;i<horizontal;i++){desktopNativeMouse.up=event.horizontal>0;desktopNativeMouse.down=event.horizontal<0;desktopClient.sendMouseState(desktopNativeMouse,false);desktopNativeMouse.up=desktopNativeMouse.down=false;desktopClient.sendMouseState(desktopNativeMouse,false);}desktopKeyState(65505,false,'wheel');}
};
function updateDesktopClipboard(){const b=$('desk-clipboard-receive');if(b)b.disabled=!desktopClient||!desktopClipboardAvailable;}
function configureDesktopInput(client,generation){
 const display=client.getDisplay().getElement();display.tabIndex=0;display.setAttribute('aria-label','远程桌面硬件键盘输入');display.addEventListener('pointerdown',()=>{if(desktopInputRemote)display.focus({preventScroll:true});});
 // Let phone-target mouse events retain browser defaults, ahead of Guacamole's
 // unconditional preventDefault handlers. Touch input remains available.
 for(const type of ['mousedown','mouseup','mousemove','wheel','contextmenu'])display.addEventListener(type,event=>{if(!desktopInputRemote)event.stopImmediatePropagation();},true);
 desktopKeyboard=new Guacamole.Keyboard(display);desktopKeyboard.onkeydown=desktopBrowserKeyDown;desktopKeyboard.onkeyup=desktopBrowserKeyUp;
 client.onclipboard=(stream,mime)=>{
  if(mime!=='text/plain'){stream.sendAck('Only plain text clipboard is supported',0x0100);return;}
  let text='',bytes=0,failed=false;const reader=new Guacamole.StringReader(stream);
  reader.ontext=chunk=>{if(failed||generation!==desktopGeneration)return;bytes+=new TextEncoder().encode(chunk).length;if(bytes>DESKTOP_CLIPBOARD_LIMIT){failed=true;text='';desktopRemoteClipboard='';desktopClipboardAvailable=false;updateDesktopClipboard();stream.sendAck('Clipboard exceeds 16 KiB',0x030D);return;}text+=chunk;stream.sendAck('OK',0);};
  reader.onend=()=>{if(!failed&&generation===desktopGeneration){desktopRemoteClipboard=text;desktopClipboardAvailable=true;updateDesktopClipboard();}};
  stream.sendAck('Ready for bounded plain text',0);
 };
 updateDesktopClipboard();
}
window.addEventListener('blur',()=>{desktopShortcutHeld=false;releaseDesktopInput();setNativeDesktopInput(false);});
window.addEventListener('focus',()=>setNativeDesktopInput(true));
document.addEventListener('visibilitychange',()=>{if(document.hidden){releaseDesktopInput();setNativeDesktopInput(false);}else setNativeDesktopInput(true);});
document.addEventListener('focusin',()=>{if(desktopEditorFocused())releaseDesktopInput();setNativeDesktopInput(true);});
document.addEventListener('focusout',()=>setTimeout(()=>setNativeDesktopInput(true),0));
window.addEventListener('error',()=>desktopTrace?.event('window-error'));
window.addEventListener('unhandledrejection',()=>desktopTrace?.event('decode-error'));
window.stopDesktop=function(){resetDesktopResizeRequest();desktopShortcutHeld=false;local('desktopInputShortcut','').catch(()=>{});releaseDesktopInput();setNativeDesktopInput(false);desktopRemoteClipboard='';desktopClipboardAvailable=false;updateDesktopClipboard();desktopKeyboard?.reset();desktopKeyboard=null;desktopBrowserMouse=null;desktopScaling=null;desktopEdgeProbe?.dispose();desktopEdgeProbe=null;local('desktopRendering','default').catch(()=>{});leaveDesktopFullscreen();desktopGeneration++;const sid=desktopId;desktopId=null;if(desktopClient){try{desktopClient.disconnect();}catch(e){}desktopClient=null;}if(sid)api('/api/desktop/close/'+sid,{}).catch(()=>{});$('screen').replaceChildren();$('screen').style.width='';$('screen').style.height='';$('desktop-session').hidden=true;document.querySelector('.desktop-intro').hidden=false;$('desktop-connect').disabled=false;$('desktop-connect').textContent='连接桌面';$('desktop-text').value='';desktopConnecting=false;};
let fullscreenDesktop=false,manualFullscreen=false,fullscreenDismissed=false,deviceLandscape=null,resizeDesktopTimer=null,desktopResizeFailureTimer=null,desktopResizeKey='',desktopResizeAttempts=0,desktopResizeReported=false;
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
 updateNativeDesktopRegion();
}
function scheduleDesktopResize(){
 clearTimeout(resizeDesktopTimer);
 if(!desktopClient)return;
 const generation=desktopGeneration;
 resizeDesktopTimer=setTimeout(()=>{if(generation===desktopGeneration)resizeRemoteDesktop();},350);
}
function showDesktopControls(show){document.body.classList.toggle('desktop-controls-open',show);$('desk-controls').setAttribute('aria-expanded',String(show));$('desk-controls').textContent=show?'收起':'控件';updateNativeDesktopRegion();}
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
function resetDesktopResizeRequest(){
 clearTimeout(resizeDesktopTimer);clearTimeout(desktopResizeFailureTimer);desktopResizeFailureTimer=null;desktopResizeKey='';desktopResizeAttempts=0;desktopResizeReported=false;
}
function armDesktopResizeFailure(size,key){
 if(desktopResizeFailureTimer!==null||desktopResizeReported)return;
 const generation=desktopGeneration;
 desktopResizeFailureTimer=setTimeout(()=>{
  desktopResizeFailureTimer=null;if(generation!==desktopGeneration||!desktopClient||desktopResizeKey!==key)return;
  const actual=desktopClient.getDisplay(),wanted=desktopRequestedSize();
  if(wanted.width===size.width&&wanted.height===size.height&&(actual.getWidth()!==size.width||actual.getHeight()!==size.height)){
   desktopResizeReported=true;$('desktop-status').textContent='远端未确认 '+size.width+' × '+size.height+' · 当前 '+actual.getWidth()+' × '+actual.getHeight();
   toast('远端未确认新分辨率，当前画面保持不变；该桌面服务可能不支持动态调整');desktopTrace?.event('resize-unconfirmed');
  }
 },1600);
}
function resizeRemoteDesktop(attempt=0){
 if(!desktopClient||!$('keyboard-box').hidden||desktopEditorFocused())return;
 const d=desktopClient.getDisplay();if(!d.getWidth()||!d.getHeight())return;
 const size=desktopRequestedSize(),key=desktopGeneration+':'+size.width+','+size.height;
 if(desktopResizeKey!==key){resetDesktopResizeRequest();desktopResizeKey=key;attempt=0;}
 if(d.getWidth()===size.width&&d.getHeight()===size.height){clearTimeout(resizeDesktopTimer);clearTimeout(desktopResizeFailureTimer);desktopResizeFailureTimer=null;desktopResizeReported=false;return;}
 // Server size notifications may acknowledge a clamped/original size. Retain
 // the same target's budget across those callbacks instead of restarting it.
 attempt=Math.max(attempt,desktopResizeAttempts);
 if(attempt>=5){armDesktopResizeFailure(size,key);return;}
 desktopResizeAttempts=attempt+1;desktopTrace?.sentSize(size.width,size.height);desktopClient.sendSize(size.width,size.height);clearTimeout(resizeDesktopTimer);
 if(desktopResizeAttempts<5){const generation=desktopGeneration;resizeDesktopTimer=setTimeout(()=>{if(generation===desktopGeneration)resizeRemoteDesktop(desktopResizeAttempts);},800*desktopResizeAttempts);}
 else armDesktopResizeFailure(size,key);
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
 const {width,height}=desktopRequestedSize(true);const data=await api('/api/desktop/open',{width,height});if(generation!==desktopGeneration){api('/api/desktop/close/'+data.id,{}).catch(()=>{});return;}desktopId=data.id;
 const tunnel=new Guacamole.Tunnel(),parser=new Guacamole.Parser();let writes='',writing=false,flushTimer=null;
 const trace=desktopTrace;
 parser.oninstruction=(opcode,args)=>{trace.received(opcode,args);if(tunnel.oninstruction)tunnel.oninstruction(opcode,args);};
 const fail=message=>{if(generation!==desktopGeneration)return;toast(message);stopDesktop();};
 const flush=async()=>{if(writing||!writes||generation!==desktopGeneration)return;writing=true;const chunk=writes;writes='';try{await api('/api/desktop/write/'+data.id,{data:chunk});}catch(e){fail(e.message);}finally{writing=false;if(writes)flush();}};
 tunnel.sendMessage=(...args)=>{if(generation!==desktopGeneration)return;writes+=args.map(v=>{const s=String(v);return Array.from(s).length+'.'+s;}).join(',')+';';if(writes.length>30000){fail('输入队列已满，请重新连接');return;}clearTimeout(flushTimer);flushTimer=setTimeout(flush,20);};
 tunnel.connect=()=>{tunnel.uuid=data.id;tunnel.setState(Guacamole.Tunnel.State.OPEN);(async()=>{while(generation===desktopGeneration){try{const response=await api('/api/desktop/read/'+data.id);if(generation!==desktopGeneration)break;if(response.data)parser.receive(response.data);}catch(e){fail(e.message);break;}}})();};
 tunnel.disconnect=()=>{clearTimeout(flushTimer);tunnel.setState(Guacamole.Tunnel.State.CLOSED);};
 desktopInputRemote=true;$('desk-input-target').textContent='键鼠：远程';$('desk-input-target').setAttribute('aria-pressed','true');
 desktopClient=new Guacamole.Client(tunnel);const client=desktopClient,display=client.getDisplay();configureDesktopInput(client,generation);$('screen').replaceChildren(display.getElement());$('desktop-session').hidden=false;document.querySelector('.desktop-intro').hidden=true;$('desktop-status').textContent='正在等待服务器桌面…';
 positionDesktopCursor(display);
 desktopScaling=configureDesktopScaling(display,desktopPresentation);trace.event('presentation',{mode:desktopScaling.mode});
 const flushDisplay=display.flush;
 display.flush=function(callback,...args){return flushDisplay.call(display,()=>{trace.rendered();if(callback)callback();},...args);};
 display.getElement().addEventListener('contextlost',()=>trace.event('contextlost'),true);
 display.getElement().addEventListener('contextrestored',()=>trace.event('contextrestored'),true);
 const protocolLabel=data.protocol==='vnc'?'VNC':data.protocol==='rdp'?'RDP':'远程桌面';
 display.onresize=()=>{fitDesktop();const wanted=desktopRequestedSize();if(display.getWidth()===wanted.width&&display.getHeight()===wanted.height)desktopResizeReported=false;scheduleDesktopResize();$('desktop-status').textContent='已连接 · '+protocolLabel+' · '+display.getWidth()+' × '+display.getHeight()+(desktopResizeReported?' · 分辨率请求未确认':'');};client.onerror=e=>fail('桌面连接中断：'+(e.message||'请重试'));client.onstatechange=state=>{if(state===Guacamole.Client.State.CONNECTED){clearTimeout(resizeDesktopTimer);resizeDesktopTimer=setTimeout(resizeRemoteDesktop,100);}};
 desktopEdgeProbe=new DesktopEdgeProbe(()=>{
  if(document.body.classList.contains('desktop-controls-open')||document.body.classList.contains('desktop-sampling'))return {window:{available:false,reason:'controls-open'}};
  return desktopSample(client);
 });const edgeProbe=desktopEdgeProbe;
 const sendMouse=(state,hardware=false)=>{if(hardware&&!desktopInputRemote)return;client.sendMouseState(state,true);edgeProbe.observe(display.getWidth(),display.getHeight(),display.cursorX,display.cursorY,display.getScale());};
 desktopMouse=new Guacamole.Mouse.Touchpad(display.getElement());desktopMouse.onmousedown=desktopMouse.onmouseup=desktopMouse.onmousemove=state=>sendMouse(state);
 const mouse=desktopBrowserMouse=new Guacamole.Mouse(display.getElement());mouse.onmousedown=mouse.onmouseup=mouse.onmousemove=state=>sendMouse(state,true);
 await local('desktopInputShortcut',desktopId).catch(()=>{});if(generation!==desktopGeneration)return;
 client.connect();setNativeDesktopInput(true);zoomed=false;syncDesktopLayout();
 }catch(e){toast(e.message);stopDesktop();}finally{desktopConnecting=false;$('desktop-connect').disabled=false;$('desktop-connect').textContent='连接桌面';}};
$('desk-disconnect').onclick=stopDesktop;$('desk-fit').onclick=()=>{zoomed=false;fitDesktop();scheduleDesktopResize();};$('desk-zoom').onclick=()=>{zoomed=!zoomed;fitDesktop();};
function desktopViewportChanged(){desktopTrace?.event('viewport',{width:innerWidth,height:innerHeight});requestAnimationFrame(fitDesktop);if(fullscreenDesktop)scheduleDesktopResize();}
window.addEventListener('resize',desktopViewportChanged);if(window.visualViewport)visualViewport.addEventListener('resize',desktopViewportChanged);
if(window.ResizeObserver)new ResizeObserver(desktopViewportChanged).observe($('screen-scroll'));
$('desk-keyboard').onclick=()=>{$('keyboard-box').hidden=!$('keyboard-box').hidden;if(!$('keyboard-box').hidden){showDesktopControls(true);$('desktop-text').focus();}else{$('desktop-text').blur();scheduleDesktopResize();}setNativeDesktopInput(true);requestAnimationFrame(fitDesktop);};
function sendKey(key){if(desktopClient){desktopKeyState(key,true,'tap');desktopKeyState(key,false,'tap');}}
document.querySelectorAll('[data-key]').forEach(b=>b.onclick=()=>sendKey(Number(b.dataset.key)));
$('send-text').onclick=()=>{if(!desktopClient)return;const text=$('desktop-text').value;if(text.length>2000){toast('一次最多发送 2000 个字符');return;}for(const c of text){const cp=c.codePointAt(0);sendKey(cp===10?65293:cp<=255?cp:0x01000000|cp);}$('desktop-text').value='';};
$('desk-right').onclick=()=>{if(!desktopClient)return;let s=new Guacamole.Mouse.State(desktopMouse?.currentState?.x||0,desktopMouse?.currentState?.y||0,false,false,true,false,false);desktopClient.sendMouseState(s,true);s.right=false;desktopClient.sendMouseState(s,true);};
for(const [label,key]of[['↑',65362],['↓',65364],['←',65361],['→',65363]]){const b=element('button',label);b.setAttribute('aria-label',label+' 键');b.onclick=()=>sendKey(key);document.querySelector('.keys').append(b);}
const ctrl=element('button','Ctrl+C');ctrl.onclick=()=>{if(desktopClient){desktopKeyState(65507,true,'shortcut');sendKey(99);desktopKeyState(65507,false,'shortcut');}};document.querySelector('.keys').append(ctrl);

for(const [name,label,key]of[['ctrl','Ctrl',65507],['alt','Alt',65513],['shift','Shift',65505],['super','Super',65515]]){
 const button=element('button',label);button.dataset.modifier=name;button.setAttribute('aria-pressed','false');button.setAttribute('aria-label',label+' 锁定键');
 button.onclick=()=>{if(!desktopClient)return;const pressed=button.getAttribute('aria-pressed')!=='true';desktopKeyState(key,pressed,'sticky');button.setAttribute('aria-pressed',String(pressed));};document.querySelector('.keys').append(button);
}
const releaseKeys=element('button','释放按键');releaseKeys.id='desk-release-keys';releaseKeys.onclick=releaseDesktopInput;document.querySelector('.keys').append(releaseKeys);
const clipboardSend=element('button','发送手机剪贴板');clipboardSend.id='desk-clipboard-send';
clipboardSend.onclick=async()=>{
 if(!desktopClient)return;const client=desktopClient,generation=desktopGeneration;clipboardSend.disabled=true;
 try{if(generation!==desktopGeneration)return;const result=await local('desktopClipboardRead');if(generation!==desktopGeneration)return;const text=result.text;if(typeof text!=='string'||new TextEncoder().encode(text).length>DESKTOP_CLIPBOARD_LIMIT)throw new Error('剪贴板文字最多 16 KiB');const writer=new Guacamole.StringWriter(client.createClipboardStream('text/plain'));writer.onack=status=>{if(status.isError()&&generation===desktopGeneration)toast('远程桌面拒绝剪贴板');};writer.sendText(text);writer.sendEnd();toast('文字已发送到远程剪贴板');}catch(e){toast(e.message);}finally{clipboardSend.disabled=false;setNativeDesktopInput(true);}
};
const clipboardReceive=element('button','复制远程剪贴板');clipboardReceive.id='desk-clipboard-receive';clipboardReceive.disabled=true;
clipboardReceive.onclick=async()=>{if(!desktopClient||!desktopClipboardAvailable)return;const generation=desktopGeneration,text=desktopRemoteClipboard;try{if(generation!==desktopGeneration)return;await local('desktopClipboardWrite',text);toast('远程文字已复制到手机');}catch(e){toast(e.message);}finally{setNativeDesktopInput(true);}};
document.querySelector('.keys').append(clipboardSend,clipboardReceive);

async function desktopSample(client){
 const display=client.getDisplay(),canvas=display.flatten(),ctx=canvas.getContext('2d'),box=$('screen').getBoundingClientRect();
 const root=display.getElement().firstElementChild,layer=display.getDefaultLayer(),backing=layer.getCanvas(),b=root.getBoundingClientRect(),style=getComputedStyle(root);
 const sample={remote:[display.getWidth(),display.getHeight()],viewport:[innerWidth,innerHeight],frame:[box.x,box.y,box.width,box.height],scale:display.getScale(),cursor:[display.cursorX,display.cursorY],presentation:{mode:desktopScaling?.mode||'transform',frame:[b.x,b.y,b.width,b.height],backing:[backing.width,backing.height],transform:style.transform,zoom:style.zoom},columns:sampleDesktopColumns(canvas.width,canvas.height,(x,y)=>ctx.getImageData(x,y,1,1).data)};
 try{sample.window=await local('desktopProbe',{cssWidth:innerWidth,cssHeight:innerHeight,x:box.x,y:box.y,width:box.width,height:box.height});}
 catch(e){sample.window={available:false,reason:'native-bridge'};}
 return sample;
}
function showDesktopReport(report){
 const body=sheet('桌面显示诊断');body.append(element('p','鼠标进入边缘或角落时会自动记录显示统计，不打开控件、不主动重绘，也不保存截图、按键或桌面文字。手动检查仍可能让黑块恢复；复制诊断会同时包含最近四次边缘记录。'));
 const presentation=element('button',desktopScaling?.mode==='layout'?'切回旧版缩放':'使用布局缩放','primary');presentation.id='desk-presentation-mode';
 presentation.onclick=()=>{if(!desktopClient||!desktopScaling)return;desktopPresentation=desktopScaling.setMode(desktopScaling.mode==='layout'?'transform':'layout');localStorage.setItem('desktop-presentation',desktopPresentation);desktopTrace?.event('presentation',{mode:desktopPresentation});$('sheet').close();fitDesktop();toast(desktopPresentation==='layout'?'已使用布局缩放，请观察右侧画面':'已恢复旧版缩放');};
 body.append(presentation,element('p','布局缩放用于排查旋转或分辨率变化后的黑块。可随时切回旧版，无需重连。','footnote'));
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
  const report={version:'0.6.0-beta.6',build:27,mode:desktopRenderMode,cursorPositioning:'layout',sampling:{controlsHidden:true,mayTriggerRepaint:true,automaticEdgeCapture:true},edges:desktopEdgeProbe?.snapshot()||[],before,after,trace:desktopTrace.snapshot()};
  try{localStorage.setItem('desktop-last-report',JSON.stringify(report));}catch(e){}
  showDesktopReport(report);
 }catch(e){toast('画面仍在调整，请稍后再检查');}finally{document.body.classList.remove('desktop-sampling');button.disabled=false;}
};
