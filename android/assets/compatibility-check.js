// SPDX-License-Identifier: Apache-2.0
// Keep this check readable by old WebViews even when the app scripts cannot parse.
(function(){
 try{
  var supported=typeof window.TextEncoder==='function'&&typeof Promise==='function'&&typeof Map==='function'
   &&typeof Object.hasOwn==='function'&&typeof Array.prototype.at==='function'
   &&typeof Element.prototype.replaceChildren==='function'&&typeof window.matchMedia==='function'
   &&typeof window.matchMedia('(orientation: landscape)').addEventListener==='function';
  return {supported:supported,ready:supported&&window.desktopSettingsReady===true&&typeof window.resumeApp==='function'&&typeof window.stopDesktop==='function'};
 }catch(error){return {supported:false,ready:false};}
})()
