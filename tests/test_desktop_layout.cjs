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
