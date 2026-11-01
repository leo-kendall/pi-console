const assert=require('node:assert/strict');
const {fitScale,desktopSize}=require('../android/assets/desktop-layout.js');
assert.equal(fitScale(844,390,1280,800,false),390/800);
assert.equal(fitScale(390,844,1280,800,false),390/1280);
assert.equal(fitScale(844,390,1280,800,true),1);
assert.equal(fitScale(0,390,1280,800,false),1);
assert.deepEqual(desktopSize(856,394,2.75),{width:2354,height:1084},'High density phone must not be limited to 2x CSS pixels');
assert.deepEqual(desktopSize(1280,720,3),{width:2560,height:1440},'Adaptive desktop must remain within the server ceiling');
for(const [w,h,dpr] of [[844,390,2],[915,412,3],[390,844,2],[1920,1080,2]]){
 const s=desktopSize(w,h,dpr);assert(s.width>=640&&s.width<=2560);assert(s.height>=480&&s.height<=1440);
 assert(Math.abs(s.width/s.height-w/h)<.005);
}
// GNOME/FreeRDP negotiates even sizes. Avoid repeatedly requesting an odd size
// which the server cannot acknowledge exactly on high-density Android phones.
for(const [w,h,density] of [[821,394,3],[873,393,2.75],[412,915,2.625]]){
 const size=desktopSize(w,h,density);
 assert.equal(size.width%2,0,'Remote width must be codec-aligned');
 assert.equal(size.height%2,0,'Remote height must be codec-aligned');
 assert(Math.abs(size.width/size.height-w/h)<.006,'Alignment changed the aspect ratio');
}

console.log('Desktop fit, adaptive resolution and codec alignment tests passed');

const {requestedDesktopSize,fixedDesktopAspect,checkedDesktopResolution}=require('../android/assets/desktop-layout.js');
assert.equal(typeof requestedDesktopSize,'function','Resolution selection must support auto, fixed and aspect-constrained sizes');
assert.deepEqual(requestedDesktopSize('1920,1080','original',392,802,3),{width:1920,height:1080},'Fixed size ignores phone orientation/density');
assert.deepEqual(requestedDesktopSize('auto','16:9',800,450,2),{width:1600,height:900});
assert.deepEqual(requestedDesktopSize('auto','4:3',800,450,2),{width:1200,height:900});
assert.deepEqual(requestedDesktopSize('auto','16:10',800,450,2),{width:1440,height:900});
assert.deepEqual(fixedDesktopAspect(1280,800,'16:9'),{width:1280,height:720});
assert.deepEqual(fixedDesktopAspect(2560,1440,'4:3'),{width:1920,height:1440},'Ratio conversion respects server height ceiling');
assert.deepEqual(fixedDesktopAspect(640,480,'21:9'),{width:1120,height:480},'Ultrawide ratio respects minimum height');
assert.deepEqual(fixedDesktopAspect(1920,1080,'16:10'),{width:1920,height:1200});
assert.deepEqual(checkedDesktopResolution('2560,1440'),{width:2560,height:1440});
for(const bad of ['639,480','2562,1440','1920,1442','1921,1080','1920,1079','auto','1920x1080','1e3,800','NaN,800'])assert.throws(()=>checkedDesktopResolution(bad),'Invalid or codec-unaligned sizes must be rejected: '+bad);
for(const ratio of ['16:9','16:10','4:3','3:2','21:9'])for(const [w,h,d] of [[320,640,2.75],[818,392,3],[1920,1080,3]]){
 const size=requestedDesktopSize('auto',ratio,w,h,d),[a,b]=ratio.split(':').map(Number);
 assert(size.width>=640&&size.width<=2560&&size.height>=480&&size.height<=1440);
 assert.equal(size.width%2,0);assert.equal(size.height%2,0);assert(Math.abs(size.width/size.height-a/b)<.006,'Aspect must remain undistorted');
}
console.log('Desktop fixed/auto/aspect selections, server bounds and custom pixel validation passed');
