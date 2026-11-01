// SPDX-License-Identifier: Apache-2.0
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const controls={'resolution':{value:''},'desktop-connect':{click(){}}};
const c={window:null,addEventListener(){},setTimeout,clearTimeout,navigator:{},document:{},$:(id)=>controls[id],navigate(){},paired:false,api:null};c.window=c;vm.createContext(c);
vm.runInContext(fs.readFileSync(__dirname+'/../android/assets/guacamole.js','utf8'),c);
vm.runInContext(fs.readFileSync(__dirname+'/../android/compat/assets/setup.js','utf8'),c);
(async()=>{await c.api('/api/desktop/open',{width:1280,height:800});c.__compatIncoming='';await c.api('/api/desktop/write/offline-compat',{data:c.__compatFrame('size',2560,1440)});assert(c.__compatIncoming.includes('2560'),'Real outbound resize must drive acknowledgement');console.log('Outbound dimensions drive synthetic resize acknowledgement');})().catch(e=>{console.error(e);process.exitCode=1});
