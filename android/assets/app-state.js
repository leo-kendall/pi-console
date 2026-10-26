'use strict';
class ActionJournal {
 constructor(storage){this.storage=storage;this.key='pending-control-v2';}
 all(){try{return JSON.parse(this.storage.getItem(this.key)||'{}');}catch(e){throw new Error('操作记录无法读取，请先核实服务器状态');}}
 get(resource){return this.all()[resource]||null;}
 begin(resource,action,request){const records=this.all();if(records[resource])throw new Error('这个对象仍有待核实操作');const record={resource,action,request,id:null,state:'submitted',created:Date.now()};records[resource]=record;this.storage.setItem(this.key,JSON.stringify(records));return record;}
 attach(resource,operation){const records=this.all();if(!records[resource])return;Object.assign(records[resource],{id:operation.id,state:operation.state});this.storage.setItem(this.key,JSON.stringify(records));}
 clear(resource){const records=this.all();delete records[resource];this.storage.setItem(this.key,JSON.stringify(records));}
}
async function removePairing(revoke,forget){let confirmed=true;try{await revoke();}catch(e){confirmed=false;}await forget();return confirmed;}
if(typeof module!=='undefined')module.exports={ActionJournal,removePairing};
