const assert=require('node:assert/strict');
const {ActionJournal,removePairing}=require('../android/assets/app-state.js');
const values=new Map(),storage={getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};
const first=new ActionJournal(storage);first.begin('proxy','restart','request-123456');
const recreated=new ActionJournal(storage);assert.equal(recreated.get('proxy').request,'request-123456');assert.throws(()=>recreated.begin('proxy','restart','new-request'));
recreated.attach('proxy',{id:'operation-1',state:'running'});assert.equal(new ActionJournal(storage).get('proxy').id,'operation-1');
recreated.clear('proxy');assert.equal(recreated.get('proxy'),null);
(async()=>{let cleared=false;const confirmed=await removePairing(async()=>{throw new Error('offline');},async()=>{cleared=true;});assert.equal(confirmed,false);assert.equal(cleared,true);assert.equal(await removePairing(async()=>{},async()=>{}),true);console.log('Action recovery / offline unpair tests passed');})().catch(e=>{console.error(e);process.exitCode=1;});
