// SPDX-License-Identifier: Apache-2.0
'use strict';
const DESKTOP_RESOLUTIONS=['1280,720','1920,1080','2560,1440','1280,800','1600,900','1920,1200','1024,768','1600,1200','1920,1440'];
function desktopResolutionOption(select,value){
 if(![...select.options].some(o=>o.value===value)){
  const size=checkedDesktopResolution(value),option=element('option',size.width+' × '+size.height);option.value=value;select.append(option);
 }
}
function desktopSizeForOptions(selection,ratio,initial=false){
 if(selection!=='auto')return requestedDesktopSize(selection,ratio,1,1,1);
 if(fullscreenDesktop||initial&&(isDesktopLandscape()||manualFullscreen)){
  const viewport=$('screen-scroll'),width=fullscreenDesktop?viewport.clientWidth:innerWidth,height=fullscreenDesktop?viewport.clientHeight:innerHeight;
  return requestedDesktopSize(selection,ratio,width||innerWidth,height||innerHeight,devicePixelRatio);
 }
 // The portrait preview remains a desktop layout; fullscreen auto mode follows
 // the available native content area, including balanced cutout protection.
 return requestedDesktopSize(selection,ratio,1280,800,1);
}
function desktopRequestedSize(initial=false){return desktopSizeForOptions($('resolution').value,$('desktop-ratio').value,initial);}
function saveDesktopDisplaySettings(){
 try{localStorage.setItem('desktop-display-settings',JSON.stringify({resolution:$('resolution').value,ratio:$('desktop-ratio').value}));}catch(e){}
}
function updateDesktopRatioLabel(){
 $('desktop-ratio').options[0].textContent=$('resolution').value==='auto'?'自动 · 跟随可用区域':'保持所选分辨率比例';
}
for(const value of DESKTOP_RESOLUTIONS)desktopResolutionOption($('resolution'),value);
try{
 const saved=JSON.parse(localStorage.getItem('desktop-display-settings')||'null');
 if(saved){
  if(saved.resolution!=='auto')checkedDesktopResolution(saved.resolution);
  if(saved.ratio!=='original'&&!Object.hasOwn(DESKTOP_RATIOS,saved.ratio))throw new Error('Invalid saved ratio');
  if(saved.resolution!=='auto')desktopResolutionOption($('resolution'),saved.resolution);
  $('resolution').value=saved.resolution;$('desktop-ratio').value=saved.ratio;
 }
}catch(e){$('resolution').value='auto';$('desktop-ratio').value='original';}
updateDesktopRatioLabel();
$('resolution').onchange=()=>{$('desktop-ratio').value='original';updateDesktopRatioLabel();saveDesktopDisplaySettings();};
$('desktop-ratio').onchange=()=>{
 if($('resolution').value!=='auto'){
  const current=checkedDesktopResolution($('resolution').value),size=fixedDesktopAspect(current.width,current.height,$('desktop-ratio').value),value=size.width+','+size.height;
  desktopResolutionOption($('resolution'),value);$('resolution').value=value;
 }
 saveDesktopDisplaySettings();
};
function showDesktopDisplaySettings(){
 const body=sheet('分辨率与屏幕比例'),choice=element('select'),ratio=element('select');choice.id='desktop-size-choice';ratio.id='desktop-ratio-choice';
 for(const source of $('resolution').options){const option=element('option',source.textContent);option.value=source.value;choice.append(option);}
 const custom=element('option','自定义像素尺寸');custom.value='custom';choice.append(custom);choice.value=$('resolution').value;
 for(const source of $('desktop-ratio').options){const option=element('option',source.textContent);option.value=source.value;ratio.append(option);}ratio.value=$('desktop-ratio').value;
 const customBox=element('div'),width=element('input'),height=element('input');width.id='desktop-custom-width';height.id='desktop-custom-height';
 for(const [input,min,max] of [[width,640,2560],[height,480,1440]]){input.type='number';input.inputMode='numeric';input.min=min;input.max=max;input.step=2;}
 const current=$('resolution').value==='auto'?(desktopClient?{width:desktopClient.getDisplay().getWidth(),height:desktopClient.getDisplay().getHeight()}:{width:1920,height:1080}):checkedDesktopResolution($('resolution').value);width.value=current.width||1920;height.value=current.height||1080;
 const preview=element('p','','footnote'),error=element('p','','field-error');preview.id='desktop-display-preview';error.id='desktop-display-error';error.setAttribute('role','alert');
 function field(container,text,input){const label=element('label',text,'field-label');label.htmlFor=input.id;container.append(label,input);}
 field(body,'分辨率',choice);field(body,'屏幕比例',ratio);field(customBox,'宽度（像素）',width);field(customBox,'高度（像素）',height);body.append(customBox);
 body.append(element('p','固定分辨率不会随手机旋转改变。修改比例会更新实际像素尺寸；画面保持等比显示。自适应在全屏时匹配可用区域。','footnote'));
 const actual=desktopClient?.getDisplay();if(actual)body.append(element('p','当前远端：'+actual.getWidth()+' × '+actual.getHeight(),'footnote'));
 const selection=()=>choice.value==='custom'?width.value+','+height.value:choice.value;
 function update(){
  customBox.hidden=choice.value!=='custom';ratio.options[0].textContent=choice.value==='auto'?'自动 · 跟随可用区域':'保持所选分辨率比例';error.textContent='';
  try{const size=desktopSizeForOptions(selection(),ratio.value);preview.textContent='将请求：'+size.width+' × '+size.height;}catch(e){preview.textContent='请输入范围内的偶数像素尺寸';}
 }
 choice.onchange=()=>{if(choice.value!=='auto')ratio.value='original';update();};
 ratio.onchange=()=>{
  try{
   if(choice.value!=='auto'){
    const original=checkedDesktopResolution(selection()),size=fixedDesktopAspect(original.width,original.height,ratio.value),value=size.width+','+size.height;
    width.value=size.width;height.value=size.height;
    if(choice.value!=='custom'){desktopResolutionOption(choice,value);choice.value=value;}
   }
   update();
  }catch(e){error.textContent=e.message;}
 };
 width.oninput=height.oninput=()=>{ratio.value='original';update();};
 const apply=element('button',desktopClient?'应用到当前连接':'保存显示设置','primary');apply.id='desktop-display-apply';
 apply.onclick=()=>{
  try{
   const value=selection(),size=desktopSizeForOptions(value,ratio.value);if(value!=='auto')desktopResolutionOption($('resolution'),value);
   $('resolution').value=value;$('desktop-ratio').value=ratio.value;updateDesktopRatioLabel();saveDesktopDisplaySettings();$('sheet').close();
   $('desktop-text').blur();$('keyboard-box').hidden=true;showDesktopControls(false);setNativeDesktopInput(true);fitDesktop();
   if(desktopClient){resetDesktopResizeRequest();resizeRemoteDesktop();toast('已请求 '+size.width+' × '+size.height+'，以远端实际确认为准');}else toast('显示设置已保存');
  }catch(e){error.textContent=e.message;}
 };
 body.append(preview,error,apply);update();
}
$('desk-display').onclick=$('desktop-display-options').onclick=showDesktopDisplaySettings;
$('sheet').addEventListener('close',()=>{if(desktopClient)scheduleDesktopResize();});
