// These catch misclassifying an opaque black tile as missing canvas data,
// recording protocol secrets, and losing the pre-fault trace on reconnect.
const assert=require('node:assert/strict');
const {sampleDesktopColumns,DesktopTrace}=require('../android/assets/desktop-diagnostics.js');
const read=(x,y)=>x>=70?[0,0,0,255]:[34,34,34,255];
assert.deepEqual(sampleDesktopColumns(100,100,read),[
 {x:5,black:0,transparent:0},{x:50,black:0,transparent:0},
 {x:70,black:100,transparent:0},{x:90,black:100,transparent:0},{x:99,black:100,transparent:0}
]);
assert.equal(sampleDesktopColumns(1,1,()=>[0,0,0,0])[0].transparent,100);
assert.equal(sampleDesktopColumns(1,1,()=>[0,0,0,0])[0].black,0);
assert.deepEqual(sampleDesktopColumns(0,0,()=>{throw Error('must not read');}),[]);
// The real blank viewport uses CSS #08090b rather than pure zero black.
assert.equal(sampleDesktopColumns(100,100,()=>[8,9,11,255])[0].black,100);
assert.equal(sampleDesktopColumns(100,100,()=>[34,34,34,255])[0].black,0);
let now=100;const trace=new DesktopTrace(()=>now);
trace.received('size',['0','2464','1182']);
trace.received('blob',['17','secret-image-data']);
trace.received('name',['private-window-name']);
trace.received('clipboard',['sensitive-text']);
now=600;trace.received('sync',['private-timestamp']);
trace.rendered();now=1100;
trace.event('contextlost');trace.sentSize(1280,800);
let report=trace.snapshot();
assert.equal(report.lastReceiveAgoMs,500);assert.equal(report.lastRenderAgoMs,500);
assert.equal(report.counts.blob,1);assert.equal(report.counts.size,1);
assert.equal(report.counts.sync,1);assert.equal(report.counts.name,undefined);
assert(report.events.some(e=>e.type==='remote-size'&&e.width===2464&&e.height===1182));
assert(report.events.some(e=>e.type==='contextlost'));
assert(!JSON.stringify(report).includes('secret'));assert(!JSON.stringify(report).includes('private'));
assert(!JSON.stringify(report).includes('sensitive'));
for(let i=0;i<1000;i++)trace.event('viewport',{width:821,height:394,password:'not-allowed'});
report=trace.snapshot();assert.equal(report.events.length,120);
assert(!JSON.stringify(report).includes('not-allowed'));
trace.event('window-error',{message:'secret server contents'});
assert(!JSON.stringify(trace.snapshot()).includes('secret server'));
console.log('Desktop diagnostic opacity, privacy, timing and bounded history passed');
