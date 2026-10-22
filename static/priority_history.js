document.addEventListener('DOMContentLoaded', () => {
    const from = document.getElementById('priorityHistoryFrom');
    const to = document.getElementById('priorityHistoryTo');
    const button = document.getElementById('priorityHistoryShow');
    const target = document.getElementById('priorityHistoryContent');
    to.value = getTodayDate();
    from.value = to.value.slice(0, 8) + '01';
    button.addEventListener('click', async () => {
        if (!from.value || !to.value || from.value > to.value) {
            target.textContent = 'Выберите корректный период: дата «С» не позже даты «По».';
            return;
        }
        button.disabled = true;
        target.textContent = 'Загрузка...';
        try {
            const response = await fetch(`/api/reports/priority-history?${new URLSearchParams({from: from.value, to: to.value})}`);
            if (!(response.headers.get('content-type') || '').includes('application/json')) {
                throw new Error(`Сервер не вернул данные отчёта (HTTP ${response.status}).`);
            }
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Не удалось загрузить историю');
            const table = document.createElement('table');
            table.className = 'in-transit-table';
            table.innerHTML = '<thead><tr><th>Дата</th><th>Приоритетные объекты</th></tr></thead><tbody></tbody>';
            for (const row of data.rows) {
                const tr = table.tBodies[0].insertRow();
                tr.insertCell().textContent = row.date.split('-').reverse().join('.');
                const cell = tr.insertCell();
                cell.style.textAlign = 'left';
                if (!row.saved) cell.textContent = 'Нет сохранённых данных';
                else if (!row.objects.length) cell.textContent = 'Приоритетов нет';
                else for (const name of row.objects) {
                    const line = document.createElement('div');
                    line.textContent = name;
                    cell.appendChild(line);
                }
            }
            target.replaceChildren(table);
        } catch (error) {
            target.textContent = `Ошибка загрузки: ${error.message}`;
        } finally {
            button.disabled = false;
        }
    });
});
