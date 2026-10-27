const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync('static/report_refresh.js', 'utf8');
async function run({rateLimitPost=false, retryAfter=null, fail=false}={}) {
    let now=0, completed=0, postCalls=0, limited=false;
    const status={textContent:''}, button={disabled:false}, calls=[], sleeps=[];
    const response=(code,data,header=null)=>({status:code,ok:code===200,headers:{get:()=>header},json:async()=>data});
    const ctx={URLSearchParams, Date:class extends Date {static now(){return now;}},
        setTimeout:fn=>{throw Error('Unexpected timer');},
        fetch:async(url,options)=>{
            if(options){postCalls++;if(rateLimitPost&&postCalls===1)return response(429,{},'60');const m=JSON.parse(options.body).month;return response(200,{id:m,status:'pending'});}
            const month=new URLSearchParams(url.split('?')[1]).get('month');calls.push({month,time:now});
            if(retryAfter!==null&&!limited){limited=true;return response(429,{},retryAfter);}
            return response(200,{status:fail?'error':'completed'});
        }};
    ctx.setTimeout=(fn,delay)=>{sleeps.push(delay);now+=delay;fn();};
    vm.createContext(ctx);vm.runInContext(source,ctx);
    await ctx.refreshSavedReports('rotations',['2026-07','2026-08','2026-09','2026-10'],status,button,async()=>{completed++;});
    assert.equal(button.disabled,false);
    return{calls,sleeps,completed,postCalls,text:status.textContent};
}
(async()=>{
    let r=await run();assert.equal(r.completed,1);assert.equal(r.calls.length,4);
    assert.deepEqual(r.calls.map(x=>x.time),[30000,60000,90000,120000]);
    r=await run({retryAfter:'120'});assert.equal(r.completed,1);assert.equal(r.calls.length,5);assert(r.sleeps.includes(120000));assert.equal(r.postCalls,4);
    r=await run({retryAfter:'invalid'});assert.equal(r.completed,1);assert(r.sleeps.includes(60000));
    r=await run({rateLimitPost:true});assert.equal(r.completed,1);assert.equal(r.postCalls,5);
    r=await run({fail:true});assert.equal(r.completed,0);assert(r.text.includes('Не удалось пересчитать'));
    console.log('Polling tests passed: pacing, completed months, 429 backoff, Retry-After, request retry, error handling');
})().catch(e=>{console.error(e);process.exitCode=1;});
