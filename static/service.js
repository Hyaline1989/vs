const shiftForm = document.getElementById('serviceShiftForm');
const shiftResult = document.getElementById('serviceShiftResult');

const shiftReasonLabels = {
    sheet_missing: 'В табеле нет листа за выбранный месяц',
    sheet_ambiguous: 'В табеле несколько подходящих листов за месяц',
    layout_unknown: 'Не удалось распознать ФИО или календарь',
    calendar_incomplete: 'Этой даты нет в шапке календаря',
    source_unavailable: 'Не удалось открыть табель',
    month_not_loaded: 'Сводка за этот месяц ещё не загружена',
    object_missing: 'Объект отсутствует в сводке за этот месяц',
};

async function loadShiftAttendance(event) {
    if (event) event.preventDefault();
    const from = document.getElementById('serviceShiftFrom').value;
    const to = document.getElementById('serviceShiftTo').value;
    if (!from || !to) return;
    if (from > to) {
        shiftResult.textContent = 'Дата «По» должна быть не раньше даты «С».';
        return;
    }
    shiftResult.textContent = 'Загрузка данных…';
    try {
        const response = await fetch(`/api/service/shifts?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
        if (!response.ok) {
            if (response.status === 403) throw new Error('Нет доступа к отчёту VIP');
            const details = await response.json().catch(() => ({}));
            throw new Error(details.error || 'Не удалось загрузить отчёт');
        }
        const data = await response.json();
        if (data.status === 'not_loaded') {
            shiftResult.textContent = 'Сводки за выбранный период ещё не загружены.';
            return;
        }
        const wrapper = document.createElement('div');
        wrapper.className = 'service-table-wrap';
        const table = document.createElement('table');
        table.className = 'service-table';
        const heading = table.createTHead().insertRow();
        const objectHeading = document.createElement('th');
        objectHeading.scope = 'col';
        objectHeading.textContent = 'Объект';
        heading.appendChild(objectHeading);
        for (const date of data.dates) {
            const cell = document.createElement('th');
            cell.scope = 'col';
            cell.textContent = `${date.slice(8, 10)}.${date.slice(5, 7)}`;
            cell.title = `${date.slice(8, 10)}.${date.slice(5, 7)}.${date.slice(0, 4)}`;
            heading.appendChild(cell);
        }
        const body = table.createTBody();
        for (const object of data.objects) {
            const row = body.insertRow();
            const name = document.createElement('th');
            name.scope = 'row';
            name.textContent = object.name;
            row.appendChild(name);
            object.counts.forEach((count, index) => {
                const cell = row.insertCell();
                cell.textContent = count === null ? '—' : String(count);
                if (count === null) {
                    cell.className = 'no-data';
                    cell.title = shiftReasonLabels[object.reasons[index]] || 'Нет данных';
                }
            });
        }
        const totalRow = table.createTFoot().insertRow();
        const totalLabel = document.createElement('th');
        totalLabel.scope = 'row';
        totalLabel.textContent = 'Итого';
        totalRow.appendChild(totalLabel);
        data.totals.forEach((total, index) => {
            const cell = totalRow.insertCell();
            cell.textContent = total === null ? '—' : String(total);
            if (data.incomplete[index]) {
                cell.className = 'no-data';
                cell.title = total === null ? 'Нет данных по объектам' :
                    'Неполный итог: показана сумма по доступным объектам';
            }
        });
        wrapper.appendChild(table);
        shiftResult.replaceChildren(wrapper);
        if (data.incomplete.some(Boolean)) {
            const warning = document.createElement('p');
            warning.className = 'service-warning';
            warning.textContent = 'Выделенные итоги неполные: по объектам со знаком «—» нет данных. Наведите на знак, чтобы увидеть причину.';
            shiftResult.appendChild(warning);
        }
    } catch (error) {
        shiftResult.textContent = `Ошибка загрузки: ${error.message}`;
    }
}

shiftForm.addEventListener('submit', loadShiftAttendance);
document.getElementById('serviceShiftExport').addEventListener('click', async () => {
    const from = document.getElementById('serviceShiftFrom').value;
    const to = document.getElementById('serviceShiftTo').value;
    const status = document.getElementById('serviceShiftExportStatus');
    const button = document.getElementById('serviceShiftExport');
    if (!from || !to || from > to) {
        status.textContent = 'Выберите правильный период.';
        return;
    }
    button.disabled = true;
    status.textContent = 'Подготовка Excel…';
    try {
        const query = new URLSearchParams({from, to});
        const response = await fetch(`/api/service/shifts.xlsx?${query}`);
        if (!response.ok) {
            const details = await response.json().catch(() => ({}));
            throw new Error(details.error || `Ошибка сервера (${response.status})`);
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `smeny_po_tabelyam_${from}_${to}.xlsx`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
        status.textContent = 'Excel скачан.';
    } catch (error) {
        status.textContent = `Ошибка выгрузки: ${error.message}`;
    } finally {
        button.disabled = false;
    }
});
document.getElementById('serviceShiftRefresh').addEventListener('click', () => {
    const from = document.getElementById('serviceShiftFrom').value;
    const to = document.getElementById('serviceShiftTo').value;
    const status = document.getElementById('serviceShiftRefreshStatus');
    if (!from || !to || from > to ||
            (new Date(`${to}T12:00:00`) - new Date(`${from}T12:00:00`)) / 86400000 > 365) {
        status.textContent = 'Выберите правильный период не более 366 дней.';
        return;
    }
    const months = [];
    let year = Number(from.slice(0, 4));
    let month = Number(from.slice(5, 7));
    const last = to.slice(0, 7);
    while (`${year}-${String(month).padStart(2, '0')}` <= last) {
        months.push(`${year}-${String(month).padStart(2, '0')}`);
        month++;
        if (month > 12) { month = 1; year++; }
    }
    refreshSavedReports('shifts', months, status,
        document.getElementById('serviceShiftRefresh'), loadShiftAttendance);
});
loadShiftAttendance();
