const plannedDepartureReasonLabels = {
    sheet_missing: 'Не найден лист за выбранный месяц',
    sheet_ambiguous: 'Найдено несколько подходящих листов за месяц',
    layout_unknown: 'Не удалось распознать ФИО или календарь в табеле',
    calendar_incomplete: 'Этой даты нет в шапке календаря',
    previous_month_missing: 'Без данных прошлого месяца нельзя подтвердить новое убытие',
    source_unavailable: 'Не удалось открыть таблицу объекта',
    duplicate_names: 'Повторяющиеся строки одного человека противоречат друг другу',
};

function plannedDepartureReason(code) {
    return plannedDepartureReasonLabels[code] || 'Причина не указана в сохранённой сводке';
}

function renderPlannedDepartures(data, target) {
    const year = Number(data.month.slice(0, 4));
    const month = Number(data.month.slice(5, 7));
    const dayCount = new Date(year, month, 0).getDate();
    const wrapper = document.createElement('div');
    wrapper.className = 'departures-grid';
    const table = document.createElement('table');
    table.className = 'departures-table';
    const thead = table.createTHead();
    const heading = thead.insertRow();
    const objectHeading = document.createElement('th');
    objectHeading.scope = 'col';
    objectHeading.textContent = 'Объект';
    heading.appendChild(objectHeading);
    for (let day = 1; day <= dayCount; day++) {
        const cell = document.createElement('th');
        cell.scope = 'col';
        cell.textContent = String(day);
        cell.title = `${String(day).padStart(2, '0')}.${String(month).padStart(2, '0')}.${year}`;
        heading.appendChild(cell);
    }
    const tbody = table.createTBody();
    for (const object of data.objects) {
        const row = tbody.insertRow();
        const name = document.createElement('th');
        name.scope = 'row';
        name.textContent = object.name;
        if (object.counts.some(count => count === null)) {
            name.textContent += ' ⚠';
            name.title = 'Есть дни без достоверных данных. Наведите на «—» для причины.';
        }
        row.appendChild(name);
        object.counts.forEach((count, dayIndex) => {
            const cell = row.insertCell();
            cell.textContent = count === null ? '—' : String(count);
            if (count === null) {
                cell.className = 'no-data';
                cell.title = plannedDepartureReason(object.reasons?.[dayIndex]);
                cell.setAttribute('aria-label', `${object.name}, ${dayIndex + 1}-е число: ${cell.title}`);
            } else if (count === 0) {
                cell.className = 'zero';
            }
        });
    }
    const tfoot = table.createTFoot();
    const totalRow = tfoot.insertRow();
    const totalHeading = document.createElement('th');
    totalHeading.scope = 'row';
    totalHeading.textContent = 'Итого';
    totalRow.appendChild(totalHeading);
    data.totals.forEach((count, dayIndex) => {
        const cell = totalRow.insertCell();
        cell.textContent = count === null ? '—' : String(count);
        if (count === null) {
            cell.className = 'no-data';
            const unknown = data.objects.filter(object => object.counts[dayIndex] === null);
            const details = unknown.slice(0, 5).map(object =>
                `${object.name}: ${plannedDepartureReason(object.reasons?.[dayIndex])}`);
            if (unknown.length > 5) details.push(`И ещё ${unknown.length - 5} объект(ов)`);
            cell.title = details.join('\n');
            cell.setAttribute('aria-label', `${dayIndex + 1}-е число, итог неизвестен: ${details.join('; ')}`);
        }
    });
    wrapper.appendChild(table);
    target.replaceChildren(wrapper);
    const note = document.createElement('p');
    note.className = 'departures-note';
    note.textContent = '— означает, что точное число неизвестно; наведите на «—», чтобы узнать причину. Это не ноль.';
    if (data.updated_at) {
        const updated = new Date(data.updated_at);
        if (!Number.isNaN(updated.getTime())) note.textContent += ` Обновлено: ${updated.toLocaleString('ru-RU')}.`;
    }
    target.appendChild(note);
}

async function loadPlannedDepartures() {
    const month = document.getElementById('plannedDeparturesMonth').value;
    const target = document.getElementById('plannedDeparturesContent');
    if (!/^20\d{2}-(0[1-9]|1[0-2])$/.test(month)) {
        target.textContent = 'Выберите месяц.';
        return;
    }
    target.textContent = 'Загрузка отчёта...';
    delete target.dataset.loaded;
    try {
        const response = await fetch(`/api/reports/planned-departures?month=${encodeURIComponent(month)}`);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || `Ошибка сервера (${response.status})`);
        if (data.status === 'not_loaded') {
            target.textContent = 'За выбранный месяц данные из табелей ещё не загружены.';
            return;
        }
        if (data.status !== 'ready' || !Array.isArray(data.objects) || !Array.isArray(data.totals)) {
            throw new Error('Сервер вернул некорректный отчёт');
        }
        renderPlannedDepartures(data, target);
        target.dataset.loaded = month;
    } catch (error) {
        target.textContent = `Ошибка загрузки: ${error.message}`;
    }
}

function refreshPlannedDepartures() {
    const month = document.getElementById('plannedDeparturesMonth').value;
    const status = document.getElementById('plannedDeparturesRefreshStatus');
    if (!/^20\d{2}-(0[1-9]|1[0-2])$/.test(month)) {
        status.textContent = 'Выберите месяц.';
        return;
    }
    refreshSavedReports('departures', [month], status,
        document.getElementById('plannedDeparturesRefresh'), loadPlannedDepartures);
}
