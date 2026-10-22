async function refreshSavedReports(report, months, statusElement, button, onComplete) {
    if (button.disabled) return;
    button.disabled = true;
    const requests = [];
    try {
        statusElement.textContent = 'Запрашиваем пересчёт табелей…';
        for (const month of months) {
            const response = await fetch('/api/report-refresh/request', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({report, month}),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.error || `Ошибка сервера (${response.status})`);
            requests.push({month, id: data.id});
        }
        const deadline = Date.now() + Math.max(12, months.length * 3) * 60 * 1000;
        while (Date.now() < deadline) {
            const results = await Promise.all(requests.map(async item => {
                const query = new URLSearchParams({report, month: item.month, id: item.id});
                const response = await fetch(`/api/report-refresh/status?${query}`);
                const data = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(data.error || `Ошибка сервера (${response.status})`);
                return data.status;
            }));
            const done = results.filter(status => status === 'completed').length;
            if (results.includes('error')) throw new Error('Не удалось пересчитать табель. Попробуйте ещё раз.');
            if (done === requests.length) {
                statusElement.textContent = 'Данные обновлены.';
                await onComplete();
                return;
            }
            statusElement.textContent = `Обновление запрошено. Готово: ${done} из ${requests.length}. Обычно ожидание начинается от минуты.`;
            await new Promise(resolve => setTimeout(resolve, 5000));
        }
        throw new Error('Ожидание затянулось. Попробуйте нажать «Показать» позже.');
    } catch (error) {
        statusElement.textContent = `Ошибка обновления: ${error.message}`;
    } finally {
        button.disabled = false;
    }
}
