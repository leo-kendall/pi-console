// SPDX-License-Identifier: Apache-2.0
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../android/assets/compatibility-check.js'),'utf8');
function environment(){
 function Element(){}Element.prototype.replaceChildren=function(){};
 return {window:{desktopSettingsReady:true,resumeApp:function(){},stopDesktop:function(){},TextEncoder:function(){},matchMedia:function(){return {addEventListener:function(){}};}},Element,Object:{hasOwn:function(){}},Array:{prototype:{at:function(){}}},Promise:function(){},Map:function(){}};
}
function result(context){return JSON.parse(JSON.stringify(vm.runInNewContext(source,context)));}
assert.deepEqual(result(environment()),{supported:true,ready:true},'A capable provider may launch regardless of vendor/version name');
const incomplete=environment();incomplete.window.desktopSettingsReady=false;
assert.deepEqual(result(incomplete),{supported:true,ready:false},'App startup failures must not be mislabeled as an outdated provider');
for(const broken of [e=>delete e.window.TextEncoder,e=>e.window.matchMedia=undefined,e=>e.window.matchMedia=function(){return {};},e=>e.Object.hasOwn=undefined,e=>e.Array.prototype.at=undefined,e=>e.Element.prototype.replaceChildren=undefined]){
 const context=environment();broken(context);assert.deepEqual(result(context),{supported:false,ready:false},'Unsupported providers must show update recovery');
}
for(const broken of [e=>delete e.window.resumeApp,e=>delete e.window.stopDesktop]){
 const context=environment();broken(context);assert.deepEqual(result(context),{supported:true,ready:false},'Incomplete app scripts cannot pass recovery-only CI');
}
const throwing=environment();throwing.window.matchMedia=function(){throw Error('provider failed');};assert.deepEqual(result(throwing),{supported:false,ready:false});
console.log('WebView capability readiness separates outdated providers from app startup failure');
