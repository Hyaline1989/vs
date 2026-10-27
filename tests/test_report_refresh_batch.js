const fs=require('fs'),vm=require('vm'),assert=require('assert');
function run(count,cost,fail=false){
 let now=0,cursor=0,released=false,failed=0,claims=0;
 const ctx={Date:{now:()=>now},console:{log(){},error(){}},
 LockService:{getScriptLock:()=>({tryLock:()=>true,releaseLock:()=>{released=true;}})},
 PropertiesService:{getScriptProperties:()=>({getProperty:k=>k==='VECTOR_IMPORT_URL'?'https://example.org/api/reports/planned-departures/import':'x'.repeat(32)})},
 UrlFetchApp:{fetch:(url)=>{if(url.endsWith('/failed')){failed++;return{getResponseCode:()=>200};}claims++;return{getResponseCode:()=>200,getContentText:()=>JSON.stringify({request:cursor<count?{report:'rotations',month:'2026-07',id:'a'.repeat(32),cursor}:null})};}},
 sendRotationPart_:task=>{assert.equal(task.cursor,cursor);if(fail)throw Error('test');cursor++;now+=cost;}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('integrations/report_refresh.gs','utf8'),ctx);ctx.processReportRefreshRequests();
 assert(released);return{cursor,failed,claims};
}
assert.deepEqual(run(8,1000),{cursor:8,failed:0,claims:9});
assert.deepEqual(run(100,60000),{cursor:3,failed:0,claims:3});
assert.deepEqual(run(8,1000,true),{cursor:0,failed:1,claims:1});
console.log('Batch tests passed: multiple sources, time budget, error stop, lock release');
