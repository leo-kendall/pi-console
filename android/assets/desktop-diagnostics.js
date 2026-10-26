'use strict';
// Only aggregate samples and fixed event fields are retained. Never retain
// instructions, encoded images, typed text, credentials or session IDs.
function sampleDesktopColumns(width,height,readPixel){
 if(width<=0||height<=0)return [];
 return [5,50,70,90,99].map(x=>{
  let black=0,transparent=0;
  for(const y of [.1,.2,.4,.6,.8,.9]){
   const p=readPixel(Math.min(width-1,Math.floor(width*x/100)),Math.min(height-1,Math.floor(height*y)));
   if(p[3]===0)transparent++;
   if(p[3]>0&&p[0]<=16&&p[1]<=16&&p[2]<=16)black++;
  }
  return {x,black:Math.round(black/6*100),transparent:Math.round(transparent/6*100)};
 });
}
class DesktopTrace {
 constructor(clock=()=>performance.now()){this.clock=clock;this.start=clock();this.lastReceive=null;this.lastRender=null;this.counts={};this.events=[];}
 event(type,data={}){
  if(!['remote-size','requested-size','viewport','render-mode','contextlost','contextrestored','window-error','decode-error','inspect','repaint'].includes(type))return;
  const entry={ms:Math.round(this.clock()-this.start),type};
  for(const key of ['width','height','mode'])if(typeof data[key]==='number'&&Number.isFinite(data[key])||key==='mode'&&['software','default'].includes(data[key]))entry[key]=data[key];
  this.events.push(entry);if(this.events.length>120)this.events.shift();
 }
 received(op,args){
  this.lastReceive=this.clock();
  if(['sync','size','img','png','jpeg','blob','end','copy','rect','cfill','dispose'].includes(op))this.counts[op]=(this.counts[op]||0)+1;
  if(op==='size'&&args[0]==='0')this.event('remote-size',{width:Number(args[1]),height:Number(args[2])});
 }
 rendered(){this.lastRender=this.clock();}
 sentSize(width,height){this.event('requested-size',{width,height});}
 snapshot(){const now=this.clock();return {durationMs:Math.round(now-this.start),lastReceiveAgoMs:this.lastReceive===null?null:Math.round(now-this.lastReceive),lastRenderAgoMs:this.lastRender===null?null:Math.round(now-this.lastRender),counts:{...this.counts},events:this.events.map(e=>({...e}))};}
}
// Capture at the edge while controls stay closed. Opening the diagnostic
// sheet can repaint a damaged WebView before its pixels can be sampled.
class DesktopEdgeProbe {
 constructor(sample,{clock=()=>performance.now(),setTimer=(fn,ms)=>setTimeout(fn,ms),clearTimer=id=>clearTimeout(id)}={}){
  this.sample=sample;this.clock=clock;this.setTimer=setTimer;this.clearTimer=clearTimer;
  this.start=clock();this.lastTaken=-Infinity;this.zone='';this.entry=0;this.capturedEntry=-1;this.timer=null;this.busy=false;this.closed=false;this.samples=[];
 }
 observe(width,height,x,y,scale){
  if(this.closed||![width,height,x,y,scale].every(Number.isFinite)||width<=0||height<=0||scale<=0)return;
  const margin=Math.max(4,Math.ceil(10/scale));
  const zone=[x<=margin?'left':x>=width-1-margin?'right':'',y<=margin?'top':y>=height-1-margin?'bottom':''].filter(Boolean).join('-');
  if(zone!==this.zone){
   this.zone=zone;this.entry++;
   if(this.timer!==null){this.clearTimer(this.timer);this.timer=null;}
  }
  this.schedule();
 }
 schedule(){
  if(this.closed||!this.zone||this.busy||this.timer!==null||this.entry===this.capturedEntry)return;
  const zone=this.zone,entry=this.entry;
  this.timer=this.setTimer(async()=>{
   this.timer=null;if(this.closed)return;
   this.lastTaken=this.clock();this.busy=true;this.capturedEntry=entry;const ms=Math.round(this.lastTaken-this.start);
   try{
    const sample=await this.sample();
    if(!this.closed)this.samples.push({ms,edge:zone,sample:JSON.parse(JSON.stringify(sample))});
   }catch(error){if(!this.closed)this.samples.push({ms,edge:zone,sample:{window:{available:false,reason:'edge-probe-failed'}}});}
   finally{this.busy=false;if(this.samples.length>4)this.samples.splice(0,this.samples.length-4);this.schedule();}
  },Math.max(120,1200-(this.clock()-this.lastTaken)));
 }
 snapshot(){return JSON.parse(JSON.stringify(this.samples));}
 dispose(){this.closed=true;if(this.timer!==null)this.clearTimer(this.timer);this.timer=null;}
}
if(typeof module!=='undefined')module.exports={sampleDesktopColumns,DesktopTrace,DesktopEdgeProbe};
