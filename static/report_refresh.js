async function refreshSavedReports(report, months, statusElement, button, onComplete) {
    if (button.disabled) return;
    button.disabled = true;
    const requests = [];
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
    // Не более одного запроса статуса за 30 секунд независимо от числа месяцев.
    const pollInterval = 30000;
    const deadline = Date.now() + (report === 'rotations' ? Math.max(120, months.length * 30) : Math.max(120, months.length * 3)) * 60 * 1000;
    async function fetchWithBackoff(url, options) {
        let attempts = 0;
        while (Date.now() < deadline) {
            const response = await fetch(url, options);
            if (response.status !== 429) return response;
            const retryAfter = response.headers.get('Retry-After');
            let delay = Math.min(900000, 60000 * (2 ** Math.min(attempts++, 4)));
            if (retryAfter) {
                const seconds = Number(retryAfter);
                const requested = Number.isFinite(seconds) ? seconds * 1000 : Date.parse(retryAfter) - Date.now();
                if (Number.isFinite(requested)) delay = Math.max(delay, requested);
            }
            if (Date.now() + delay >= deadline) break;
            statusElement.textContent = `Сервер ограничил частоту запросов. Повторим проверку через ${Math.ceil(delay / 60000)} мин. Уже принятые задания продолжаются; повторно нажимать «Обновить данные» не нужно.`;
            await sleep(delay);
        }
        throw new Error('Проверка статуса отложена из-за лимита запросов. Позже нажмите «Показать». Это не отменяет принятые задания.');
    }
    try {
        statusElement.textContent = 'Запрашиваем пересчёт табелей…';
        for (const month of months) {
            const response = await fetchWithBackoff('/api/report-refresh/request', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({report, month}),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.error || `Ошибка сервера (${response.status})`);
            requests.push({month, id: data.id, status: data.status || 'pending'});
        }
        let cursor = 0;
        while (Date.now() < deadline) {
            const done = requests.filter(item => item.status === 'completed').length;
            if (requests.some(item => item.status === 'error')) throw new Error('Не удалось пересчитать табель. Попробуйте ещё раз.');
            if (done === requests.length) {
                statusElement.textContent = 'Данные обновлены.';
                await onComplete();
                return;
            }
            statusElement.textContent = `Обновление запрошено. Готово месяцев: ${done} из ${requests.length}. ` +
                (report === 'rotations' ? 'Табели обрабатываются последовательно пакетами. Можно закрыть страницу — расчёт продолжится.' : 'Обычно ожидание начинается от минуты.');
            await sleep(pollInterval);
            if (Date.now() >= deadline) break;
            while (requests[cursor % requests.length].status === 'completed') cursor++;
            const item = requests[cursor++ % requests.length];
            const query = new URLSearchParams({report, month: item.month, id: item.id});
            const response = await fetchWithBackoff(`/api/report-refresh/status?${query}`);
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.error || `Ошибка сервера (${response.status})`);
            item.status = data.status;
        }
        throw new Error('Ожидание затянулось. Попробуйте нажать «Показать» позже.');
    } catch (error) {
        statusElement.textContent = `Ошибка обновления: ${error.message}`;
    } finally {
        button.disabled = false;
    }
}
