document.addEventListener('DOMContentLoaded', () => {
    const el = id => document.getElementById(id);
    const money = value => Number(value).toLocaleString('ru-RU') + ' ₽';
    const date = value => value.split('-').reverse().join('.');
    function table(headers, rows) {
        const result = document.createElement('table');
        result.className = 'in-transit-table payroll-result-table';
        const head = result.createTHead().insertRow();
        headers.forEach(text => { const th = document.createElement('th'); th.textContent = text; head.appendChild(th); });
        const body = result.createTBody();
        rows.forEach(row => { const tr = body.insertRow(); row.forEach((text, index) => { const cell = tr.insertCell(); cell.textContent = text; if (index === row.length - 1) cell.className = 'money-cell'; }); });
        return result;
    }
    el('payrollMonth').value = getTodayDate().slice(0, 7);
    el('payrollLoad').addEventListener('click', async () => {
        const button = el('payrollLoad');
        if (!el('payrollMonth').value) { el('payrollStatus').textContent = 'Выберите месяц.'; return; }
        button.disabled = true;
        el('payrollStatus').textContent = 'Получаем данные из Битрикс24 и рассчитываем начисления...';
        el('payrollSummary').replaceChildren(); el('payrollDetails').replaceChildren(); el('payrollDetailsTitle').hidden = true;
        try {
            const response = await fetch('/api/reports/candidate-rates/calculation?' + new URLSearchParams({month: el('payrollMonth').value}));
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Не удалось выполнить расчёт');
            const summary = data.summary.map(row => [row.staff, String(row.candidates), row.unrated ? String(row.unrated) : '0', money(row.amount)]);
            if (summary.length) el('payrollSummary').replaceChildren(table(['Сотрудник','Кандидатов с 1 сменой','Без ставки','Начислено'], summary));
            const details = data.rows.map(row => [row.staff,row.candidate,row.object,date(row.directed_date),date(row.shift_date),row.amount === null ? row.problem : money(row.amount)]);
            if (details.length) {
                el('payrollDetailsTitle').hidden = false;
                el('payrollDetails').replaceChildren(table(['Сотрудник','Кандидат','Объект','Направлен','1 смена','Начисление'], details));
            }
            el('payrollStatus').textContent = summary.length
                ? `Кандидатов: ${data.totals.candidates}. Начислено: ${money(data.totals.amount)}. Без ставки: ${data.totals.unrated}.`
                : 'За выбранный месяц нет кандидатов, отработавших первую смену.';
            if (data.excluded?.length) {
                el('payrollStatus').appendChild(document.createTextNode(` Не начислено из-за некорректных дат: ${data.excluded.length}.`));
                const heading = document.createElement('h3'); heading.textContent = 'Проверить даты в Битрикс24';
                el('payrollDetails').append(heading, table(['ID сделки', 'Кандидат', 'Причина'], data.excluded.map(row => [row.deal_id, row.candidate, row.problem])));
            }
        } catch (error) {
            el('payrollStatus').textContent = 'Ошибка: ' + error.message;
        } finally { button.disabled = false; }
    });
});
