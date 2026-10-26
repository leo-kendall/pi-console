// SPDX-License-Identifier: Apache-2.0
// Edge captures must work without opening controls or repainting the page.
const assert=require('node:assert/strict');
const {DesktopEdgeProbe}=require('../android/assets/desktop-diagnostics.js');
function fixture(sample){let now=0,next=0;const timers=new Map();const probe=new DesktopEdgeProbe(sample,{clock:()=>now,setTimer:(fn,ms)=>{timers.set(++next,{fn,due:now+ms});return next;},clearTimer:id=>timers.delete(id)});return {probe,timers,advance:ms=>{now+=ms},fire:async()=>{const [id,item]=timers.entries().next().value;timers.delete(id);now=Math.max(now,item.due);await item.fn();}};}
(async()=>{
 let calls=0;const f=fixture(async()=>{calls++;return {cursor:[2559,1439],window:{available:true,pixelCopy:0,columns:[]}};});
 f.probe.observe(2560,1440,1280,720,.27);assert.equal(f.timers.size,0);
 f.probe.observe(2560,1440,2559,1439,.27);assert.equal(f.timers.size,1);
 f.probe.observe(2560,1440,2558,1438,.27);assert.equal(f.timers.size,1);await f.fire();assert.equal(calls,1);assert.equal(f.probe.snapshot()[0].edge,'right-bottom');
 f.probe.observe(2560,1440,1280,720,.27);f.probe.observe(2560,1440,0,0,.27);assert.equal(calls,1,'Rapid edge changes must not flood native PixelCopy');assert.equal(f.timers.size,1,'Edge entered during cooldown must get a trailing sample without another movement');await f.fire();assert.equal(calls,2);assert.equal(f.probe.snapshot().at(-1).edge,'left-top');
 f.advance(1500);f.probe.observe(2560,1440,1280,720,.27);f.probe.observe(2560,1440,0,0,.27);f.probe.observe(2560,1440,1280,720,.27);assert.equal(f.timers.size,0,'Leaving edge cancels pending sample');
 for(let i=0;i<8;i++){f.advance(1500);f.probe.observe(2560,1440,1280,720,.27);f.probe.observe(2560,1440,0,0,.27);await f.fire();}
 assert.equal(f.probe.snapshot().length,4,'Edge history must be bounded');
 const snapshot=f.probe.snapshot();snapshot[0].sample.window.available=false;assert.equal(f.probe.snapshot()[0].sample.window.available,true);
 let resolve;const g=fixture(()=>new Promise(r=>{resolve=r}));g.probe.observe(2560,1440,0,0,.27);const running=g.fire();await Promise.resolve();g.probe.dispose();resolve({window:{available:true}});await running;assert.deepEqual(g.probe.snapshot(),[],'Late results from closed desktop must be discarded');
 let finishFirst,asyncCalls=0;
 const busy=fixture(()=>{asyncCalls++;return asyncCalls===1?new Promise(r=>finishFirst=r):Promise.resolve({window:{available:true}});});
 busy.probe.observe(2560,1440,0,0,.27);const first=busy.fire();await Promise.resolve();busy.probe.observe(2560,1440,2559,1439,.27);finishFirst({window:{available:true}});await first;
 assert.equal(busy.timers.size,1,'A different edge entered during native capture must be sampled after the current request');await busy.fire();assert.equal(asyncCalls,2);assert.equal(busy.probe.snapshot().at(-1).edge,'right-bottom');
 const h=fixture(async()=>{throw Error('private-token-and-desktop-text')});h.probe.observe(2560,1440,0,0,.27);await h.fire();assert.equal(h.probe.snapshot()[0].sample.window.reason,'edge-probe-failed');assert(!JSON.stringify(h.probe.snapshot()).includes('private-token'));
 const p=fixture(async()=>({}));p.probe.observe(2560,1440,0,0,.27);p.probe.dispose();assert.equal(p.timers.size,0);p.probe.observe(2560,1440,2559,1439,.27);assert.equal(p.timers.size,0);
 console.log('Automatic corner sampling: no controls/repaint needed, throttled, bounded, cancelable, private errors and late-result isolation passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
