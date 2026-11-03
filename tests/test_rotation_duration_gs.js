const fs=require('fs'), vm=require('vm'), assert=require('assert'), crypto=require('crypto');
const context={console, monthDays_:()=>31,isWork_:v=>Number(v)>0,
    sourceIdForMonth_:source=>source[1],
    looksLikePerson_:v=>String(v).trim().split(/\s+/).length>=2,
    chooseMonthSheet_:()=>({sheet}),
    locateCalendar_:()=>({nameCol:1,dayCol:3,firstDataRow:2,available:Array(31).fill(true)}),
    Utilities:{computeHmacSha256Signature:(v,k)=>Array.from(crypto.createHmac('sha256',k).update(v).digest())},
    SpreadsheetApp:{openById:()=>({})}};
const row=(name,role,marks)=>[name,role,...marks,...Array(31-marks.length).fill('')];
const values=[Array(33).fill(''),row('Иванов Иван','',['11','ОВ']),row('Иванов Иван','',['11','11']),row('Петров Пётр','Менеджер',['11']),row('Сидоров Сидор','',[''])];
const sheet={getLastRow:()=>values.length,getMaxColumns:()=>33,getRange:()=>({getDisplayValues:()=>values,getBackgrounds:()=>values.map(r=>r.map(()=>'#fff'))})};
vm.createContext(context);vm.runInContext(fs.readFileSync('integrations/rotation_duration.gs','utf8'),context);
const result=context.rotationSource_(['Объект','id'],2026,8,'secret');
assert.equal(result.people.length,3);
assert.equal(result.people[0].marks[0].length,1);
assert(result.people[0].marks[1].includes('W'));
assert.equal(result.people[1].excluded,true);
assert.equal(context.rotationPersonId_(' Петров  Пётр ','secret'),context.rotationPersonId_('ПЕТРОВ ПЕТР','secret'));
context.SpreadsheetApp.openById=()=>{throw Error('denied');};
assert.equal(context.rotationSource_(['Объект','id'],2026,8,'secret').reason,'source_unavailable');
console.log('Rotation Apps Script tests passed');
