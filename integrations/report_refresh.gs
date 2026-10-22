// Проверяет очередь Вектора раз в минуту. Без запроса табели не открываются.
function processReportRefreshRequests() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const properties = PropertiesService.getScriptProperties();
    const importUrl = properties.getProperty('VECTOR_IMPORT_URL') || '';
    const key = properties.getProperty('VECTOR_IMPORT_KEY') || '';
    const suffix = '/api/reports/planned-departures/import';
    if (!importUrl.endsWith(suffix) || !importUrl.startsWith('https://') || key.length < 32) {
      throw new Error('Проверьте VECTOR_IMPORT_URL и VECTOR_IMPORT_KEY');
    }
    const base = importUrl.slice(0, -suffix.length);
    const headers = {'X-Vector-Import-Key': key};
    const pending = UrlFetchApp.fetch(base + '/api/report-refresh/pending', {
      method: 'get', headers, muteHttpExceptions: true,
    });
    if (pending.getResponseCode() !== 200) {
      throw new Error('Очередь Вектора вернула HTTP ' + pending.getResponseCode());
    }
    const task = JSON.parse(pending.getContentText()).request;
    if (!task) return;
    try {
      if (!['departures', 'shifts'].includes(task.report) ||
          !/^20\d{2}-(0[1-9]|1[0-2])$/.test(task.month) ||
          !/^[0-9a-f]{32}$/.test(task.id)) {
        throw new Error('Некорректный запрос на пересчёт');
      }
      const year = Number(task.month.slice(0, 4));
      const month = Number(task.month.slice(5, 7));
      const payload = task.report === 'departures' ?
        buildPlannedDepartures_(year, month) : buildShiftAttendance_(year, month);
      const endpoint = task.report === 'departures' ?
        suffix : '/api/service/shifts/import';
      const response = UrlFetchApp.fetch(base + endpoint, {
        method: 'post', contentType: 'application/json',
        headers: {'X-Vector-Import-Key': key, 'X-Vector-Refresh-Id': task.id},
        payload: JSON.stringify(payload), muteHttpExceptions: true,
      });
      if (response.getResponseCode() !== 200) {
        throw new Error('Импорт вернул HTTP ' + response.getResponseCode());
      }
      console.log('Обновлён отчёт ' + task.report + ' за ' + task.month);
    } catch (error) {
      console.error('Ошибка пересчёта ' + task.report + ' за ' + task.month + ': ' + error);
      const failed = UrlFetchApp.fetch(base + '/api/report-refresh/failed', {
        method: 'post', contentType: 'application/json', headers,
        payload: JSON.stringify(task), muteHttpExceptions: true,
      });
      if (failed.getResponseCode() !== 200) {
        console.error('Не удалось отметить ошибку пересчёта: HTTP ' + failed.getResponseCode());
      }
    }
  } finally {
    lock.releaseLock();
  }
}

// Включать только после загрузки новых серверных файлов Вектора.
function enableMinuteReportRefresh() {
  if (ScriptApp.getProjectTriggers().some(trigger =>
      trigger.getHandlerFunction() === 'processReportRefreshRequests')) return;
  ScriptApp.newTrigger('processReportRefreshRequests').timeBased().everyMinutes(1).create();
  console.log('Проверка запросов на обновление раз в минуту включена');
}
