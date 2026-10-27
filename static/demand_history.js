(() => {
    const el=id=>document.getElementById(id);
    const node=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
    let serial=0,opened=false;
    async function load(event){
        if(event)event.preventDefault();
        if(!el('demandHistoryForm').reportValidity())return;
        const from=el('demandHistoryFrom').value,to=el('demandHistoryTo').value;
        const root=el('demandHistoryResult'),id=++serial;
        if(from>to || (new Date(to)-new Date(from))/86400000>365){root.textContent='Выберите период не более 366 дней.';return;}
        root.textContent='Загрузка…';
        try{
            const r=await fetch('/api/service/demand-history?'+new URLSearchParams({from,to}));
            const data=await r.json().catch(()=>({}));
            if(!r.ok)throw Error(data.error||`Ошибка сервера (${r.status})`);
            if(id!==serial)return;
            root.replaceChildren();
            if(!data.objects.length){root.textContent='За выбранный период ещё нет сохранённой истории потребности.';return;}
            root.append(node('p','Последняя запись в выбранном периоде: '+new Date(data.last_saved_at).toLocaleString('ru-RU')));
            if(data.objects.some(o=>(o.legacy||[]).some(Boolean)))root.append(node('p','† Перенесённые старые значения: прежний механизм сохранял максимумы по категориям, а не последнее значение за день. Дата последней записи может быть датой переноса. Остальные значения — последняя сохранённая потребность.'));
            const wrap=node('div','');wrap.className='service-table-wrap';
            const table=node('table','');table.className='service-table';
            const head=table.createTHead().insertRow();head.append(node('th','Объект'));
            data.dates.forEach((day,i)=>{const th=node('th',day.slice(8)+'.'+day.slice(5,7)+(data.priority_saved[i]?'':' *'));th.title=day+(data.priority_saved[i]?'':' — приоритеты не зафиксированы');head.append(th);});
            const body=table.createTBody();
            for(const o of data.objects){const row=body.insertRow();const name=node('th',o.name);name.scope='row';row.append(name);
                o.counts.forEach((count,i)=>{const c=row.insertCell();c.textContent=count===null?'—':String(count)+(o.legacy?.[i]?' †':'');
                    c.title=count===null?'Потребность за этот день не сохранена':`Потребность: ${count}`;
                    if(o.legacy?.[i])c.title+='; перенесено из старого учёта, не последнее значение дня';
                    if(o.priorities[i]===true){c.className='demand-priority';c.title+='; зафиксирован приоритет';}
                    else if(count===null)c.className='no-data';
                    if(o.priorities[i]===null)c.title+='; приоритеты не зафиксированы';
                });
            }
            const total=table.createTFoot().insertRow();total.append(node('th','Итого'));
            data.totals.forEach((v,i)=>{const c=total.insertCell();c.textContent=v===null?'—':String(v);if(data.incomplete[i]){c.className='no-data';c.title='Неполный итог: сумма только сохранённых значений';}});
            wrap.append(table);root.append(wrap);
            if(data.incomplete.some(Boolean))root.append(node('p','Выделенные итоги неполные: по части объектов нет сохранённых значений.'));
            if(data.priority_saved.some(v=>!v))root.append(node('p','* Приоритеты на эту дату не зафиксированы. Отсутствие красной подсветки не означает, что объект не был приоритетным.'));
        }catch(e){if(id===serial)root.textContent='Ошибка загрузки: '+e.message;}
    }
    el('demandHistoryForm').addEventListener('submit',load);
    document.querySelector('[data-vip="demand"]').addEventListener('click',()=>{if(!opened){opened=true;load();}});
})();
