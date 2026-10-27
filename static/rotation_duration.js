(() => {
    const el = id => document.getElementById(id);
    let mode = 'objects', metric = 'mean', report = null, serial = 0, opened = false;
    const end = new Date(el('rotationTo').value + 'T12:00:00');
    const month = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
    el('rotationFrom').value = month(new Date(end.getFullYear(), end.getMonth()-3, 1)) + '-01';
    el('rotationCohort').value = month(new Date(end.getFullYear(), end.getMonth()-2, 1));
    const reasons = {sheet_missing:'Нет листа месяца', sheet_ambiguous:'Неоднозначные листы месяца', layout_unknown:'Не распознан календарь или ФИО', calendar_incomplete:'Неполный календарь', source_unavailable:'Табель недоступен', month_not_loaded:'Месяц не загружен'};
    const node = (tag, text) => { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; return n; };
    function query() {
        if (!el('rotationForm').reportValidity()) throw new Error('Заполните даты');
        const from=el('rotationFrom').value, to=el('rotationTo').value, cohort=el('rotationCohort').value;
        if(from>to || (new Date(to)-new Date(from))/86400000>365 || cohort<from.slice(0,7) || cohort>to.slice(0,7)) throw new Error('Выберите период до 366 дней и месяц когорты внутри периода');
        return new URLSearchParams({from,to,cohort,mode});
    }
    function render() {
        const root=el('rotationResult'); root.replaceChildren();
        if(report && report.loading) {
            const s=report.loading;
            const pending=s.months.some(m=>m.refresh_status==='pending');
            const failed=s.months.some(m=>m.refresh_status==='error');
            const box=node('section');box.setAttribute('aria-label','Состояние сохранённых данных');
            box.append(node('h3',s.complete?'Сохранённые сводки: все месяцы получены':'Сохранённые сводки: загрузка неполная'));
            box.append(node('p',`Месяцев: ${s.months_saved} из ${s.months_total}. Частей сводки сохранено: ${s.parts_saved}${s.parts_total===null?'':` из ${s.parts_total}`}.`));
            if(s.latest_saved_at) box.append(node('p',`Последнее сохранение месяца: ${new Date(s.latest_saved_at).toLocaleString('ru-RU')}. Самая ранняя сводка периода: ${new Date(s.oldest_saved_at).toLocaleString('ru-RU')}.`));
            if(pending)box.append(node('p','Идёт новый пересчёт. Ниже показаны ранее сохранённые данные; это не подтверждение завершения нового запроса.'));
            if(failed)box.append(node('p','Последний пересчёт части периода завершился с ошибкой. Ранее сохранённые данные доступны.'));
            const details=node('details');details.append(node('summary','Сохранение по месяцам'));
            const list=node('ul');for(const m of s.months)list.append(node('li',`${m.month}: ${m.saved?`${m.parts} частей, ${new Date(m.saved_at).toLocaleString('ru-RU')}`:'ещё не сохранён'}${m.refresh_status==='pending'?' — новый пересчёт в очереди или выполняется':m.refresh_status==='error'?' — ошибка нового пересчёта':''}`));details.append(list);box.append(details);
            if(report.status==='ready')box.append(node('p',report.partial?'Полнота данных: есть пропуски. Причины перечислены под таблицей.':'Полнота данных: в сохранённых сводках нет отмеченных пропусков.'));
            root.append(box);
        }
        if(!report || report.status==='not_loaded') { root.append(node('p','Сводки ещё не загружены. Если обновление уже запрошено, дождитесь завершения и нажмите «Показать».'));el('rotationMetrics').replaceChildren(); return; }
        const tabs=el('rotationMetrics'); tabs.replaceChildren();
        for(const m of report.metrics) {
            const b=node('button',m.title); b.type='button'; b.setAttribute('aria-pressed',String(metric===m.id));
            b.onclick=()=>{metric=m.id;render();}; tabs.append(b);
        }
        root.append(node('p',`Период: ${report.from} — ${report.to}. Когорта: ${report.cohort}. Обновлено: ${new Date(report.updated_at).toLocaleString('ru-RU')}`));
        if(report.partial) { const p=node('p','Неполные данные: показатели рассчитаны только по доступным табелям. Подробности ниже.');p.className='service-warning';root.append(p); }
        const columns=report.metrics.find(m=>m.id===metric).columns;
        const wrap=node('div');wrap.className='service-table-wrap'; const table=node('table');table.className='service-table';
        const head=node('thead'), hr=node('tr'); for(const label of [report.mode==='objects'?'Объект':'Компания',...columns.map(c=>c[1])])hr.append(node('th',label));head.append(hr);table.append(head);
        const body=node('tbody');
        for(const row of report.rows) {
            const tr=node('tr');tr.append(node('th',row.name+(row.warnings.length?' ⚠':'')));
            for(const [key] of columns) { const value=row[key]; tr.append(node('td',value===null?'Нет данных':key.endsWith('_share')?(value*100).toLocaleString('ru-RU',{maximumFractionDigits:1})+'%':value.toLocaleString('ru-RU',{maximumFractionDigits:2}))); }
            body.append(tr);
        }
        table.append(body);wrap.append(table);root.append(wrap);
        if(report.partial) { const details=node('details');details.append(node('summary','Причины неполных данных'));const ul=node('ul');for(const r of report.rows)for(let w of r.warnings){for(const [key,label] of Object.entries(reasons))w=w.replace(key,label);ul.append(node('li',r.name+': '+w));}details.append(ul);root.append(details); }
        const details=node('details');details.append(node('summary','Как считается отчёт'));const ul=node('ul');for(const n of report.notes)ul.append(node('li',n));details.append(ul);root.append(details);
    }
    async function load() {
        const id=++serial;
        try {const q=query();el('rotationResult').textContent='Загрузка…';const response=await fetch('/api/service/rotations?'+q);const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||`Ошибка сервера ${response.status}`);if(id!==serial)return;report=data;render();}
        catch(e){if(id===serial)el('rotationResult').textContent='Ошибка: '+e.message;}
    }
    document.querySelectorAll('[data-vip]').forEach(b=>b.onclick=()=>{
        document.querySelectorAll('[data-vip]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
        document.querySelectorAll('.vip-pane').forEach(p=>p.hidden=p.id!==`vip-${b.dataset.vip}`);
        if(b.dataset.vip==='rotations'&&!opened){opened=true;load();}
    });
    document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{mode=b.dataset.mode;document.querySelectorAll('[data-mode]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));load();});
    el('rotationForm').onsubmit=e=>{e.preventDefault();load();};
    el('rotationRefresh').onclick=()=>{
        try {const q=query(), months=[];let d=new Date(q.get('from').slice(0,7)+'-01T12:00:00');while(month(d)<=q.get('to').slice(0,7)){months.push(month(d));d.setMonth(d.getMonth()+1);}refreshSavedReports('rotations',months,el('rotationRefreshStatus'),el('rotationRefresh'),load);}
        catch(e){el('rotationRefreshStatus').textContent=e.message;}
    };
    el('rotationExport').onclick=async()=>{
        const button=el('rotationExport');button.disabled=true;
        try {const q=query();el('rotationExportStatus').textContent='Подготовка Excel…';const r=await fetch('/api/service/rotations.xlsx?'+q);if(!r.ok){const data=await r.json().catch(()=>({}));throw new Error(data.error||'Не удалось скачать Excel');}const url=URL.createObjectURL(await r.blob());const a=node('a');a.href=url;a.download=`Продолжительность_${q.get('mode')}_${q.get('from')}_${q.get('to')}.xlsx`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);el('rotationExportStatus').textContent='Excel скачан.';}
        catch(e){el('rotationExportStatus').textContent=e.message;}finally{button.disabled=false;}
    };
})();
