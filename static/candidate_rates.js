document.addEventListener('DOMContentLoaded', () => {
    const el = id => document.getElementById(id);
    const status = text => { el('ratesStatus').textContent = text; };
    let pending = null;
    let busy = false;
    const invalidate = () => { pending = null; el('ratesSave').hidden = true; el('ratesChanges').replaceChildren(); };
    const money = value => value === null ? '—' : value.toLocaleString('ru-RU') + ' ₽';
    const dateLabel = value => value.split('-').reverse().join('.');
    async function api(url, options) {
        const response = await fetch('/api/reports/candidate-rates' + url, options);
        if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Сервер не вернул данные. Проверьте вход в Вектор.');
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Ошибка запроса');
        return data;
    }
    function table(headers, rows) {
        const result = document.createElement('table');
        result.className = 'in-transit-table';
        const head = result.createTHead().insertRow();
        headers.forEach(text => { const th = document.createElement('th'); th.textContent = text; head.appendChild(th); });
        const body = result.createTBody();
        rows.forEach(row => { const tr = body.insertRow(); row.forEach(text => { tr.insertCell().textContent = text; }); });
        return result;
    }
    async function load() {
        const data = await api('?' + new URLSearchParams({month: el('ratesMonth').value}));
        const previous = el('ratesObject').value;
        el('ratesObject').replaceChildren();
        data.rows.forEach(row => el('ratesObject').add(new Option(row.name, row.object_id)));
        if (data.rows.some(row => String(row.object_id) === previous)) el('ratesObject').value = previous;
        const grid = document.createElement('table');
        grid.className = 'departures-table';
        const header = grid.createTHead().insertRow();
        ['Объект', ...data.days.map(dateLabel)].forEach(text => { const th = document.createElement('th'); th.textContent = text; header.appendChild(th); });
        const body = grid.createTBody();
        for (const row of data.rows) {
            const tr = body.insertRow();
            const name = document.createElement('th'); name.textContent = row.name; tr.appendChild(name);
            for (const cell of row.cells) {
                const td = tr.insertCell();
                const button = document.createElement('button'); button.type = 'button';
                button.textContent = cell.amount !== null ? money(cell.amount) : '—';
                button.style.cssText = 'font:inherit;color:inherit;background:transparent;border:0;cursor:pointer;white-space:nowrap';
                button.title = row.name + ', ' + dateLabel(cell.day) + ': ' + (cell.comment || 'Ставка ещё не сохранена');
                button.addEventListener('click', () => {
                    if (busy) return;
                    el('ratesObject').value = row.object_id;
                    el('ratesFrom').value = el('ratesTo').value = cell.day;
                    el('ratesAmount').value = cell.amount ?? cell.suggestion ?? '';
                    el('ratesComment').value = cell.comment;
                    invalidate();
                });
                td.appendChild(button);
            }
        }
        el('ratesCalendar').replaceChildren(grid);
    }
    function selection() {
        return {object_id: Number(el('ratesObject').value), from: el('ratesFrom').value, to: el('ratesTo').value};
    }
    function lock(value) {
        busy = value;
        ['ratesLoad','ratesPreview','ratesSave','ratesHistory','ratesObject','ratesFrom','ratesTo','ratesMode','ratesAmount','ratesComment','ratesMonth'].forEach(id => { el(id).disabled = value; });
    }
    async function run(action) {
        if (busy) return;
        lock(true); status('Загрузка...');
        try { await action(); } catch (error) { invalidate(); status(error.message); } finally { lock(false); }
    }
    for (const id of ['ratesObject','ratesFrom','ratesTo','ratesMode','ratesAmount','ratesComment','ratesMonth']) el(id).addEventListener('input', invalidate);
    el('ratesLoad').addEventListener('click', () => run(async () => { invalidate(); await load(); status('Календарь загружен'); }));
    el('ratesPreview').addEventListener('click', () => run(async () => {
        invalidate();
        const payload = {...selection(), mode: el('ratesMode').value, amount: Number(el('ratesAmount').value), comment: el('ratesComment').value.trim()};
        if (payload.mode === 'manual' && (!el('ratesAmount').value || !Number.isInteger(payload.amount) || payload.amount < 0 || payload.amount > 1000000 || !payload.comment)) throw new Error('Введите целую сумму от 0 до 1 000 000 ₽ и причину изменения.');
        const data = await api('/preview?' + new URLSearchParams(selection()));
        const rows = data.cells.map(cell => {
            const next = payload.mode === 'manual' ? payload.amount : cell.amount ?? cell.suggestion;
            return [dateLabel(cell.day), money(cell.amount), money(next), payload.mode === 'confirm' && cell.amount !== null ? 'Сохранённая ставка останется' : next === null ? 'Нет данных — пропуск' : 'Будет сохранено'];
        });
        el('ratesChanges').replaceChildren(table(['Дата направления','Было','Станет','Действие'], rows));
        pending = {...payload, revision: data.revision};
        el('ratesSave').hidden = false; status('Проверьте суммы перед сохранением');
    }));
    el('ratesSave').addEventListener('click', () => run(async () => {
        if (!pending) throw new Error('Сначала посмотрите изменения');
        const result = await api('', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(pending)});
        invalidate();
        status(`Сохранено дней: ${result.changed}. Без изменений: ${result.skipped}.`);
        try { await load(); } catch (error) { status(`Ставки сохранены, но календарь не обновился: ${error.message}`); }
    }));
    el('ratesHistory').addEventListener('click', () => run(async () => {
        const data = await api('/history?' + new URLSearchParams(selection()));
        el('ratesAudit').replaceChildren(table(['Дата направления','Было','Стало','Автор','Когда','Комментарий'], data.rows.map(row => [dateLabel(row.day),money(row.old_amount),money(row.new_amount),row.actor_name,new Date(row.changed_at).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'}) + ' МСК',row.new_comment])));
        status(data.rows.length ? `Правок: ${data.rows.length}` : 'Правок за этот период нет');
    }));
    const today = getTodayDate();
    el('ratesMonth').value = today.slice(0,7);
    el('ratesFrom').value = el('ratesTo').value = today;
    function pane(rates) {
        el('prioritiesPane').hidden = rates; el('candidateRatesPane').hidden = !rates;
        el('showPriorities').setAttribute('aria-pressed', String(!rates));
        el('showCandidateRates').setAttribute('aria-pressed', String(rates));
        if (rates && !el('ratesObject').options.length) el('ratesLoad').click();
    }
    el('showPriorities').addEventListener('click', () => pane(false));
    el('showCandidateRates').addEventListener('click', () => pane(true));
});
