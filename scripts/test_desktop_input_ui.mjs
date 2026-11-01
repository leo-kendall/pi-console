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
async function waitFor(expr){for(let i=0;i<60;i++){if(await evaluate(expr))return;await delay(100);}throw Error('Timeout: '+expr+' '+await evaluate("JSON.stringify({active:document.activeElement.id,hidden:document.hidden,editor:desktopEditorFocused(),sessions:inputSessions.slice(-10),errors:window.caughtErrors,sheet:$('sheet').open,keyboard:$('keyboard-box').hidden})"));}
try{
 await call('browsingContext.setViewport',{context,viewport:{width:1024,height:768},devicePixelRatio:1});
 await call('browsingContext.navigate',{context,url:'http://127.0.0.1:18777',wait:'complete'});await waitFor("page==='settings'");await call('browsingContext.activate',{context});
 await evaluate("$('server-url').value='https://console.example.test';$('save-server').click();void 0");await waitFor("!$('pair').disabled");
 await evaluate("$('pair-code').value='ABCDEF12';$('pair').click();void 0");await waitFor('paired');
 await evaluate(`window.caughtErrors=[];window.addEventListener('error',e=>caughtErrors.push(e.message));window.sent=[];window.reads=0;window.remoteFrames='';window.clipReads=0;window.clipWrites=[];window.inputSessions=[];window.inputRegions=[];const originalLocal=local;
 local=async(action,value)=>{if(action==='desktopInput'){inputSessions.push(value);return {ok:true};}if(action==='desktopInputRegion'){inputRegions.push(value);return {ok:true};}if(action==='desktopClipboardRead'){clipReads++;return {text:'explicit 📋'};}if(action==='desktopClipboardWrite'){clipWrites.push(value);return {ok:true};}return originalLocal(action,value);};
 const frame=(...parts)=>parts.map(p=>String(p).length+'.'+p).join(',')+';';
 api=async(path,body)=>{if(path==='/api/desktop/open')return {id:'desktop-test-session',protocol:'vnc'};if(path.startsWith('/api/desktop/write/')){sent.push(body.data);return {ok:true};}if(path.startsWith('/api/desktop/read/')){if(reads++===0)return {data:frame('size',0,1280,800)+frame('sync',1)};await new Promise(r=>setTimeout(r,300));const incoming=remoteFrames;remoteFrames='';return {data:incoming+frame('sync',reads)};}return {ok:true};};
 navigate('desktop');$('desktop-connect').click();void 0`);
 await waitFor('desktopClient?.getDisplay().getWidth()===1280');
 assert.equal(await evaluate("$('desktop-status').textContent.includes('VNC')"),true,'Configured protocol shown from backend response');
 await call('browsingContext.setViewport',{context,viewport:{width:818,height:392},devicePixelRatio:1});
 await evaluate('setDeviceLandscape(true);void 0');await waitFor("document.body.classList.contains('desktop-fullscreen')");await delay(100);
 await evaluate("$('desk-controls').click();void 0");await delay(40);
 assert.equal(await evaluate("(()=>{const e=$('desk-disconnect'),b=e.getBoundingClientRect();return document.elementFromPoint(b.x+b.width/2,b.y+b.height/2)?.closest('button')===e;})()"),true,'Expanded toolbar Disconnect is not obscured by target badge');
 await evaluate("$('desk-controls').click();updateNativeDesktopRegion();void 0");
 assert.equal(await evaluate("(()=>{const r=inputRegions.at(-1);return ['desk-input-target','desk-controls'].every(id=>{const b=$(id).getBoundingClientRect(),x=(b.x+b.width/2)/innerWidth,y=(b.y+b.height/2)/innerHeight;return r.exclude?.some(e=>x>=e.left&&x<e.right&&y>=e.top&&y<e.bottom);});})()"),true,'Native region excludes target badge and collapsed Controls from remote mouse capture');
 await call('browsingContext.setViewport',{context,viewport:{width:1024,height:768},devicePixelRatio:1});
 await evaluate('setDeviceLandscape(false);void 0');await delay(60);
 await evaluate("(()=>{const screen=$('screen'),saved=screen.getBoundingClientRect;screen.getBoundingClientRect=()=>({left:-100,top:-100,right:-20,bottom:-20});updateNativeDesktopRegion();screen.getBoundingClientRect=saved;})();void 0");
 assert.equal(await evaluate("['left','top','right','bottom'].every(k=>inputRegions.at(-1)[k]>=0&&inputRegions.at(-1)[k]<=1)"),true,'Fully offscreen display disables native mouse region safely');
 await evaluate('updateNativeDesktopRegion();void 0');
 assert.equal(await evaluate('clipReads'),0,'No clipboard polling at connect');
 assert.equal(await evaluate("Boolean(document.querySelector('[data-modifier=ctrl]'))"),true,'Sticky modifiers exist');
 await evaluate("document.querySelector('[data-modifier=ctrl]').click();document.querySelector('[data-key=\"65293\"]').click();void 0");await delay(80);
 assert.equal(await evaluate("sent.join('').includes('3.key,5.65507,1.1;')"),true,'Sticky control down');
 assert.equal(await evaluate("document.querySelector('[data-modifier=ctrl]').getAttribute('aria-pressed')"),'true');
 await evaluate("desktopNativeInput({session:desktopId,type:'key',keysym:97,down:true});desktopNativeInput({session:desktopId,type:'key',keysym:97,down:false});void 0");await delay(80);
 assert.equal(await evaluate("sent.join('').includes('3.key,2.97,1.1;')"),true,'Hardware key down');
 await evaluate("desktopNativeInput({session:desktopId,type:'reset'});void 0");await delay(80);
 assert.equal(await evaluate("document.querySelector('[data-modifier=ctrl]').getAttribute('aria-pressed')"),'false','Focus loss clears sticky control');
 assert.equal(await evaluate("sent.join('').includes('3.key,5.65507,1.0;')"),true,'Focus loss releases control');
 // A target switch releases both native and browser state, then leaves phone input local.
 await evaluate("sent=[];desktopNativeInput({session:desktopId,type:'key',keysym:97,down:true});desktopKeyboard.press(98);desktopMouse.press('left');$('desk-input-target')?.click();void 0");await delay(100);
 assert.equal(await evaluate("$('desk-input-target')?.getAttribute('aria-pressed')"),'false','Target button switches hardware input to phone');
 assert.equal(await evaluate("sent.join('').includes('3.key,2.97,1.0;')&&sent.join('').includes('3.key,2.98,1.0;')"),true,'Target switch releases held native and browser keys');
 assert.equal(await evaluate('desktopMouse.currentState.left'),false,'Target switch releases held mouse button');
 assert.equal(await evaluate("inputSessions.at(-1)"),'','Phone target disables native forwarding');
 await evaluate("sent=[];desktopNativeInput({session:desktopId,type:'key',keysym:99,down:true});desktopClient.getDisplay().getElement().dispatchEvent(new KeyboardEvent('keydown',{key:'c',code:'KeyC',keyCode:67,bubbles:true,cancelable:true}));desktopBrowserMouse.onmousemove(new Guacamole.Mouse.State(30,40,true,false,false,false,false));void 0");await delay(750);
 assert.equal(await evaluate("/3.key|5.mouse/.test(sent.join(''))"),false,'Phone target blocks native and browser keyboard/mouse input and repeat');
 await evaluate("window.phoneKey=new KeyboardEvent('keydown',{key:'a',code:'KeyA',keyCode:65,bubbles:true,cancelable:true});window.phoneWheel=new WheelEvent('wheel',{deltaY:100,bubbles:true,cancelable:true});desktopClient.getDisplay().getElement().dispatchEvent(phoneKey);desktopClient.getDisplay().getElement().dispatchEvent(phoneWheel);$('desk-clipboard-send').click();void 0");await waitFor('clipReads===1');
 assert.equal(await evaluate('phoneKey.defaultPrevented||phoneWheel.defaultPrevented'),false,'Phone target preserves normal browser keyboard and wheel defaults');
 assert.equal(await evaluate("inputSessions.at(-1)"),'','Explicit clipboard action does not enable remote hardware capture');
 await evaluate('clipReads=0;void 0');
 await evaluate("desktopNativeInput({session:'old-session',type:'toggle-target'});void 0");
 assert.equal(await evaluate("$('desk-input-target').getAttribute('aria-pressed')"),'false','Stale session cannot change target');
 await evaluate("desktopNativeInput({session:desktopId,type:'toggle-target'});void 0");await waitFor("inputSessions.at(-1)===desktopId");
 assert.equal(await evaluate("$('desk-input-target').getAttribute('aria-pressed')"),'true','Native shortcut restores remote target');
 await evaluate("desktopNativeInput({session:desktopId,type:'key',keysym:100,down:true});desktopNativeInput({session:desktopId,type:'key',keysym:100,down:false});void 0");await delay(80);
 assert.equal(await evaluate("sent.join('').includes('3.key,3.100,1.1;')"),true,'Remote hardware input resumes');
 // Browser fallback consumes the chord and repeated Space, including modifier-first release.
 await evaluate("(()=>{const target=desktopClient.getDisplay().getElement();target.focus();window.targetSpace=new KeyboardEvent('keydown',{key:' ',code:'Space',keyCode:32,ctrlKey:true,altKey:true,bubbles:true,cancelable:true});target.dispatchEvent(targetSpace);target.dispatchEvent(new KeyboardEvent('keydown',{key:' ',code:'Space',keyCode:32,ctrlKey:true,altKey:true,repeat:true,bubbles:true,cancelable:true}));target.dispatchEvent(new KeyboardEvent('keyup',{key:' ',code:'Space',keyCode:32,bubbles:true,cancelable:true}));})();void 0");
 assert.equal(await evaluate('targetSpace.defaultPrevented'),true,'Toggle Space is consumed');
 assert.equal(await evaluate("$('desk-input-target').getAttribute('aria-pressed')"),'false','Holding Space toggles only once');
 await evaluate("$('desk-input-target').click();void 0");await waitFor("inputSessions.at(-1)===desktopId");
 await evaluate("$('desk-clipboard-send').click();void 0");await waitFor('clipReads===1');await delay(100);
 assert.equal(await evaluate("sent.join('').includes('9.clipboard')"),true,'Real Guacamole clipboard stream used');
 await evaluate("remoteFrames='9.clipboard,2.42,10.text/plain;4.blob,2.42,8.cmVtb3Rl;3.end,2.42;';void 0");await waitFor("!$('desk-clipboard-receive').disabled");
 assert.equal(await evaluate('clipWrites.length'),0,'Remote clipboard never automatically writes phone clipboard');
 await evaluate("$('desk-clipboard-receive').click();void 0");await waitFor('clipWrites.length===1');assert.equal(await evaluate('clipWrites[0]'),'remote');
 await evaluate("$('desk-keyboard').click();void 0");await delay(30);assert.equal(await evaluate("inputSessions[inputSessions.length-1]"),'','Editor disables native capture '+await evaluate("JSON.stringify({active:document.activeElement.id,hidden:$('keyboard-box').hidden,editor:desktopEditorFocused(),sessions:inputSessions.slice(-8)})"));
 // Headless Firefox does not emit OS focus events for scripted focus/blur.
 await evaluate("$('desktop-text').blur();document.dispatchEvent(new FocusEvent('focusout',{bubbles:true}));void 0");await waitFor("inputSessions[inputSessions.length-1]==='desktop-test-session'");assert.equal(await evaluate("inputSessions[inputSessions.length-1]"),'desktop-test-session','Leaving editor restores native capture');
 await evaluate(`(()=>{const b=$('screen').getBoundingClientRect();desktopNativeInput({session:desktopId,type:'mouse',x:(b.x+20)/innerWidth,y:(b.y+30)/innerHeight,buttons:3,wheel:1});desktopNativeInput({session:desktopId,type:'mouse',x:(b.x+20)/innerWidth,y:(b.y+30)/innerHeight,buttons:0,wheel:0});})()`);await delay(80);
 assert.equal(await evaluate("sent.join('').includes('5.mouse')"),true,'Hardware mouse reaches Guacamole');
 // Combined modifier ownership: physical Ctrl release must keep sticky Ctrl held.
 await evaluate("sent=[];document.querySelector('[data-modifier=ctrl]').click();desktopNativeInput({session:desktopId,type:'key',keysym:65507,down:true});desktopNativeInput({session:desktopId,type:'key',keysym:65507,down:false});void 0");await delay(80);
 assert.equal(await evaluate("sent.join('').includes('3.key,5.65507,1.0;')"),false,'Physical release preserves sticky modifier');
 await evaluate("$('desk-release-keys').click();void 0");await delay(80);assert.equal(await evaluate("sent.join('').includes('3.key,5.65507,1.0;')"),true);
 // A browser-held key must stop its Guacamole repeat timer when released.
 await evaluate("desktopKeyboard.press(97);$('desk-release-keys').click();void 0");await delay(100);
 await evaluate("sent=[];void 0");await delay(750);
 assert.equal(await evaluate("sent.join('').includes('3.key,2.97,1.1;')"),false,'Release stops browser keyboard auto-repeat');
 await evaluate("desktopMouse.press('left');$('desk-release-keys').click();void 0");await delay(80);
 assert.equal(await evaluate('desktopMouse.currentState.left'),false,'Release clears a held touch mouse button');
 // Clipboard size is bounded in UTF-8 bytes; old content is cleared on overflow.
 await evaluate("remoteFrames='9.clipboard,2.43,10.text/plain;4.blob,2.43,'+btoa('x'.repeat(16385)).length+'.'+btoa('x'.repeat(16385))+';3.end,2.43;';void 0");await waitFor("$('desk-clipboard-receive').disabled");
 assert.equal(await evaluate('desktopRemoteClipboard'),'', 'Oversized remote clipboard is discarded');
 const sentBefore=await evaluate("sent.join('').split('9.clipboard').length");
 await evaluate("const previousLocal=local;local=async(a,v)=>a==='desktopClipboardRead'?{text:'🚀'.repeat(5000)}:previousLocal(a,v);$('desk-clipboard-send').click();void 0");await delay(150);
 assert.equal(await evaluate("sent.join('').split('9.clipboard').length"),sentBefore,'Oversized UTF-8 phone text never sends a stream');
 const before=await evaluate("sent.join('').includes('3.key,2.98,1.1;')");await evaluate("desktopNativeInput({session:'old-session',type:'key',keysym:98,down:true});void 0");await delay(80);assert.equal(await evaluate("sent.join('').includes('3.key,2.98,1.1;')"),before,'Old native session ignored');
 await evaluate("stopDesktop();void 0");assert.equal(await evaluate("inputSessions[inputSessions.length-1]"),'','Disconnect disables native capture');
 console.log('Desktop browser: real Guacamole key/modifier/mouse/clipboard, explicit clipboard permission, editor focus, reset and stale session checks passed.');
}finally{await evaluate('stopDesktop();pauseApp();void 0').catch(()=>{});await call('session.end');socket.close();}
