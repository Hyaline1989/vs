// Добавить отдельным файлом в существующий Apps Script проект табелей.
// Использует DEPARTURE_SOURCES и служебные функции из действующего скрипта.
// Передаются только агрегаты по объектам, без ФИО и телефонов.

function summarizeShiftAttendanceSource_(source, year, month) {
  const [name, id, override = {}] = source;
  const days = monthDays_(year, month);
  const empty = reason => ({name, counts: Array(days).fill(null), reasons: Array(days).fill(reason)});
  let book;
  try {
    book = SpreadsheetApp.openById(id);
  } catch (error) {
    console.log(name + ': не удалось открыть таблицу смен');
    return empty('source_unavailable');
  }
  const selected = chooseMonthSheet_(book, year, month, override);
  if (!selected.sheet) return empty(selected.warning);
  const counts = Array(days).fill(0);
  const reasons = Array(days).fill(null);
  const peopleByDay = Array.from({length: days}, () => new Set());
  const available = Array(days).fill(true);
  for (const sheet of (Array.isArray(selected.sheet) ? selected.sheet : [selected.sheet])) {
  const layout = locateCalendar_(sheet, days, override);
  if (!layout) return empty('layout_unknown');
  for (let day = 0; day < days; day++) available[day] = available[day] && layout.available[day];
  const rowCount = Math.max(0, sheet.getLastRow() - layout.firstDataRow + 1);
  if (rowCount) {
    const names = sheet.getRange(layout.firstDataRow, layout.nameCol, rowCount, 1).getDisplayValues();
    const calendar = sheet.getRange(layout.firstDataRow, layout.dayCol, rowCount, days).getDisplayValues();
    for (let row = 0; row < rowCount; row++) {
      if (!looksLikePerson_(names[row][0])) continue;
      const person = normalizeName_(names[row][0]);
      for (let day = 0; day < days; day++) {
        if (layout.available[day] && isWork_(String(calendar[row][day]).trim().toUpperCase())) {
          peopleByDay[day].add(person);
        }
      }
    }
  }
  }
  for (let day = 0; day < days; day++) {
    if (available[day]) {
      counts[day] = peopleByDay[day].size;
    } else {
      counts[day] = null;
      reasons[day] = 'calendar_incomplete';
    }
  }
  return {name, counts, reasons};
}

function buildShiftAttendance_(year, month) {
  if (!Number.isInteger(year) || year < 2020 || year > 2099 ||
      !Number.isInteger(month) || month < 1 || month > 12) {
    throw new Error('Некорректный месяц');
  }
  const period = year + '-' + String(month).padStart(2, '0');
  return {month: period, objects: DEPARTURE_SOURCES.map(source =>
    summarizeShiftAttendanceSource_(source, year, month))};
}

function previewShiftAttendance() {
  const period = Utilities.formatDate(new Date(), 'Europe/Moscow', 'yyyy-MM');
  const payload = buildShiftAttendance_(Number(period.slice(0, 4)), Number(period.slice(5, 7)));
  for (const object of payload.objects) {
    console.log(object.name + ': ' + object.counts.reduce((sum, count) => sum + (count || 0), 0) +
      ' смен за месяц; нет данных за ' + object.counts.filter(count => count === null).length + ' дней');
  }
}

function sendShiftAttendanceForMonth_(year, month) {
  const properties = PropertiesService.getScriptProperties();
  const plannedUrl = properties.getProperty('VECTOR_IMPORT_URL') || '';
  const key = properties.getProperty('VECTOR_IMPORT_KEY');
  const url = plannedUrl.replace(/\/api\/reports\/planned-departures\/import\/?$/,
    '/api/service/shifts/import');
  if (!/^https:\/\//.test(url) || url === plannedUrl || !key || key.length < 32) {
    throw new Error('Проверьте VECTOR_IMPORT_URL и VECTOR_IMPORT_KEY в свойствах скрипта');
  }
  const payload = buildShiftAttendance_(year, month);
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: {'X-Vector-Import-Key': key},
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
    validateHttpsCertificates: true,
  });
  if (response.getResponseCode() !== 200) {
    throw new Error('Вектор не принял сводку смен: HTTP ' + response.getResponseCode());
  }
  console.log('Передана сводка смен за ' + payload.month + ': объектов ' + payload.objects.length);
}

function sendShiftAttendanceAugust2026() {
  sendShiftAttendanceForMonth_(2026, 8);
}

function sendShiftAttendanceSeptember2026() {
  sendShiftAttendanceForMonth_(2026, 9);
}

function sendShiftAttendance() {
  const period = Utilities.formatDate(new Date(), 'Europe/Moscow', 'yyyy-MM');
  sendShiftAttendanceForMonth_(Number(period.slice(0, 4)), Number(period.slice(5, 7)));
}

// Включать только после проверки первой ручной отправки и установки серверных файлов.
function enableHalfHourlyShiftAttendance() {
  const exists = ScriptApp.getProjectTriggers().some(trigger =>
    trigger.getHandlerFunction() === 'sendShiftAttendance');
  if (exists) return;
  ScriptApp.newTrigger('sendShiftAttendance').timeBased().everyMinutes(30).create();
  console.log('Обновление сводки смен каждые 30 минут включено');
}
