// Исходный код для отдельного проекта Google Apps Script «Вектор — проверка ПУ и ОВ».
// Никаких ФИО и телефонов в Вектор не отправляется. Триггер не создаётся автоматически.

const DEPARTURE_SOURCES = [
  ['Форум Авто', '1LpsFXpb6wVaG4ZT7UwKoGjQS2SibRRbmUbDY182f9WI'],
  ['Летуаль', '1zzsTPmrD6yHgFiEWExKzopd-Wi2YqlyGx5PlpDyoVbY'],
  ['Яндекс Казань', '16hCX2fn5v0tg4agNE0xZIQNcSDIXXGkF'],
  ['Спортмастер', '1KbizfRCzmu-GscK-lrhkFCFjR5AV281OhNyG0HAgwFg'],
  ['Сберлогистика', '1xjX5YaPafiHwcFcvLDD89k1VfW3rYPl0zQMb37koXyc'],
  ['Птичка', '1DtZk0tCYRHn87ua5mXUtPKKifoq1LCe8zKjroMivao4'],
  ['Мяснов', '1l4zZI_7eG7ApjQJS06rFx012hXnPy74P7uO2_nOVoQY'],
  ['Мишель', '1cawqaBxv4swbRd1bAYu1rim9IUV5RYnBFvw53wTT1os'],
  ['Мираторг Хоруга', '1NTPCs6zDbbePoeDf_sztvuH2GV2SwL92vxdHwOz-Y-g'],
  ['Мейджер', '1BlXQCcD1By09gFvaHdKmrBHIGjPRHGT25axJV0q1Rg8'],
  ['БелгранКорм', '16ZjPym0g8oyvxKwxIwrBJNAB7iiBTSQplN4FISyrubc'],
  ['Агама', '1i1Tq3zBvaGacm3oZa8lDf0NFZaYd1g2o19QCGljvYRk'],
  ['Мираторг ББ', '1t9Tox2Zr_NjEPYusSUPimJC7q2vrOPbs', {mergeMiratorgShifts: true}],
  ['Индейка Калуга', '17ZFxeIh-tY6Wn4aIq2NKAivQWwhkOCtYdvfWAvsZBts', {nameCol: 2}],
  ['СДТ', '10XEsL8iY0d-wi3rKjMyJXiC7R9P56MXq', {nameCol: 4, dayCol: 13, headerRow: 2}],
  ['КуулКлевер', '1a0wu3r6U0TCCA933m8Xv5zU6ppaCKGqF'],
  ['АСКОНА', '1UFLI9J7w6ix6-o1FbnZS6jHWf8X2nRsk'],
  ['Яндекс Самара', '1fYDX5P6GulImHegnl67XVukC9mzkYkb2'],
  ['Шашлык Тамбов', '1Q6Wwm1BuUtoHh_BA79fM_50ir11FRy3D'],
  ['ФитнесШок', '1F0Ys8jQJ8TixxXAUaamGscSzi9VefOlB'],
  ['Креветки Клинский', '1AtApIPq-P4RVMTdYy9BPmSMe6rJuXluxRsItLk-BSe0'],
  ['Клинский Мясокомбинат', '1rNGTooID-_PTpYEIMkRdlygdExelHQvoqaG_g4ZPJqk']
];

const RUSSIAN_MONTHS = [
  'январ', 'феврал', 'март', 'апрел', 'май', 'июн', 'июл', 'август',
  'сентябр', 'октябр', 'ноябр', 'декабр'
];

function monthDays_(year, month) {
  return new Date(year, month, 0).getDate();
}

function chooseMonthSheet_(book, year, month, override = {}) {
  if (override.mergeMiratorgShifts) {
    return chooseMiratorgShiftSheets_(book, year, month);
  }
  const names = (override.monthSheets || {})[year + '-' + String(month).padStart(2, '0')];
  if (names) {
    const all = book.getSheets();
    const sheets = names.map(name => all.find(sheet => sheet.getName() === name));
    if (sheets.some(sheet => !sheet)) return {sheet: null, warning: 'sheet_missing'};
    return {sheet: sheets, warning: null};
  }
  const root = RUSSIAN_MONTHS[month - 1];
  const matches = book.getSheets().filter(sheet => {
    const name = sheet.getName().toLowerCase();
    const nameYear = name.match(/20\d{2}/);
    return name.includes(root) && (nameYear
      ? Number(nameYear[0]) === year
      : year === 2026);
  });
  const explicit = matches.filter(sheet => sheet.getName().includes(String(year)));
  const selected = explicit.length ? explicit : matches;
  if (!selected.length) return {sheet: null, warning: 'sheet_missing'};
  if (selected.length !== 1) return {sheet: null, warning: 'sheet_ambiguous'};
  return {sheet: selected[0], warning: null};
}

function chooseMiratorgShiftSheets_(book, year, month) {
  const monthName = [
    'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
    'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'
  ][month - 1];
  const normalize = name => name.trim().replace(/\s+/g, ' ').toLowerCase();
  const all = book.getSheets();
  const groups = ['бб {year} с 15:00', 'бб {year} с 08:00', 'крс {year}'];
  const selected = groups.map(group => {
    const expected = normalize(monthName + ' ' + group.replace('{year}', String(year)));
    const explicit = all.filter(sheet => normalize(sheet.getName()) === expected);
    // Названия без года относятся только к 2026, как и в остальных табелях.
    const yearless = normalize(monthName + ' ' + group.replace('{year}', ''));
    return explicit.length || year !== 2026 ? explicit :
      all.filter(sheet => normalize(sheet.getName()) === yearless);
  });
  if (selected.some(group => group.length > 1)) return {sheet: null, warning: 'sheet_ambiguous'};
  if (selected.some(group => group.length)) {
    // Не публикуем неполный итог, если одна из трёх согласованных смен пропала.
    if (selected.some(group => !group.length)) return {sheet: null, warning: 'sheet_missing'};
    return {sheet: selected.map(group => group[0]), warning: null};
  }
  // Старые месяцы могли храниться одним общим листом.
  const exact = all.filter(sheet => normalize(sheet.getName()) === monthName + ' ' + year);
  const single = exact.length || year !== 2026 ? exact :
    all.filter(sheet => normalize(sheet.getName()) === monthName);
  if (single.length > 1) return {sheet: null, warning: 'sheet_ambiguous'};
  return single.length ? {sheet: single[0], warning: null} : {sheet: null, warning: 'sheet_missing'};
}

function locateCalendar_(sheet, days, override) {
  const header = sheet.getRange(1, 1, Math.min(5, sheet.getMaxRows()),
    Math.min(90, sheet.getMaxColumns())).getDisplayValues();
  let nameCol = override.nameCol || 0;
  let nameRow = 0;
  let dayCol = override.dayCol || 0;
  let headerRow = override.headerRow || 0;
  let longest = 0;
  for (let r = 0; r < header.length; r++) {
    for (let c = 0; c < header[r].length; c++) {
      if (!nameCol && String(header[r][c]).trim().toUpperCase().includes('ФИО')) {
        nameCol = c + 1;
        nameRow = r + 1;
      }
      if (override.dayCol || c + 2 >= header[r].length) continue;
      if (['1', '2', '3'].every((day, offset) =>
        String(header[r][c + offset]).trim() === day)) {
        let length = 3;
        while (length < days && c + length < header[r].length &&
               String(header[r][c + length]).trim() === String(length + 1)) length++;
        if (length > longest) {
          longest = length;
          dayCol = c + 1;
          headerRow = r + 1;
        }
      }
    }
  }
  if (!nameCol || !dayCol || !headerRow) return null;
  const labels = sheet.getRange(headerRow, dayCol, 1, days).getDisplayValues()[0];
  const available = labels.map((value, index) => String(value).trim() === String(index + 1));
  if (!available[0] || !available[1] || !available[2]) return null;
  return {nameCol, dayCol, firstDataRow: Math.max(nameRow, headerRow) + 1, available};
}

function normalizeName_(value) {
  return String(value).trim().replace(/\s+/g, ' ').toUpperCase();
}

function looksLikePerson_(value) {
  const name = normalizeName_(value);
  return name.split(' ').length >= 2 &&
    !/^(ИТОГО|ВЫХОД|ЧАСЫ|ДЕНЬ|ДАННЫЕ)(\s|$)/.test(name);
}

function readPeople_(sheet, days, override) {
  const people = new Map();
  const conflictDays = new Set();
  const available = Array(days).fill(true);
  for (const part of (Array.isArray(sheet) ? sheet : [sheet])) {
  const layout = locateCalendar_(part, days, override);
  if (!layout) return null;
  for (let day = 0; day < days; day++) available[day] = available[day] && layout.available[day];
  const rowCount = Math.max(0, part.getLastRow() - layout.firstDataRow + 1);
  if (rowCount) {
    const names = part.getRange(layout.firstDataRow, layout.nameCol, rowCount, 1).getDisplayValues();
    const calendar = part.getRange(layout.firstDataRow, layout.dayCol, rowCount, days).getDisplayValues();
    for (let row = 0; row < rowCount; row++) {
      if (!looksLikePerson_(names[row][0])) continue;
      const key = normalizeName_(names[row][0]);
      const marks = calendar[row].map(value => String(value).trim().toUpperCase());
      if (!people.has(key)) {
        people.set(key, marks);
      } else {
        const existing = people.get(key);
        for (let day = 0; day < days; day++) {
          if (!existing[day]) {
            existing[day] = marks[day];
          } else if (marks[day] && existing[day] !== marks[day]) {
            if (existing[day] === '?' ||
                (isDeparture_(existing[day]) && !isDeparture_(marks[day]) &&
                 !isActive_(marks[day]) && marks[day] !== 'УБ') ||
                (!isDeparture_(existing[day]) && isDeparture_(marks[day]) &&
                 !isActive_(existing[day]) && existing[day] !== 'УБ')) {
              existing[day] = '?';
              conflictDays.add(day);
            } else if (isActive_(marks[day]) && isDeparture_(existing[day])) {
              existing[day] = marks[day];
            } else if (marks[day] === 'УБ' && isDeparture_(existing[day])) {
              existing[day] = 'УБ';
            } else if (isActive_(marks[day])) {
              existing[day] = marks[day];
            }
          }
        }
      }
    }
  }
  }
  return {people, available, conflictDays};
}

function isDeparture_(mark) {
  return mark === 'ПУ' || mark === 'ОВ';
}

function isWork_(mark) {
  return /^\d+(?:[.,]\d+)?$/.test(mark) && Number(mark.replace(',', '.')) > 0;
}

function isActive_(mark) {
  return isWork_(mark) || mark === 'В';
}

function previousState_(marks) {
  let departed = false;
  let uncertain = false;
  for (const mark of marks) {
    if (mark === '?') {
      departed = false;
      uncertain = true;
    } else if (isDeparture_(mark) || mark === 'УБ') {
      departed = true;
      uncertain = false;
    } else if (isActive_(mark)) {
      departed = false;
      uncertain = false;
    }
  }
  return {departed, uncertain};
}

function summarizeSource_(source, year, month) {
  const [name, id, override = {}] = source;
  const days = monthDays_(year, month);
  const empty = (warning) => ({
    name, counts: Array(days).fill(null), reasons: Array(days).fill(warning), warnings: [warning]
  });
  let book;
  try {
    book = SpreadsheetApp.openById(id);
  } catch (error) {
    console.log(name + ': не удалось открыть таблицу');
    return empty('source_unavailable');
  }
  const selected = chooseMonthSheet_(book, year, month, override);
  if (!selected.sheet) return empty(selected.warning);
  const current = readPeople_(selected.sheet, days, override);
  if (!current) return empty('layout_unknown');

  const previousDate = new Date(year, month - 2, 1);
  const previousYear = previousDate.getFullYear();
  const previousMonth = previousDate.getMonth() + 1;
  const previousDays = monthDays_(previousYear, previousMonth);
  const previousSelection = chooseMonthSheet_(book, previousYear, previousMonth, override);
  const previous = previousSelection.sheet
    ? readPeople_(previousSelection.sheet, previousDays, override) : null;
  const counts = Array(days).fill(0);
  const reasons = Array(days).fill(null);
  const warnings = [];
  if (!previous) warnings.push('previous_month_missing');
  if (current.conflictDays.size) warnings.push('duplicate_names');
  for (let day = 0; day < days; day++) {
    if (!current.available[day]) {
      counts[day] = null;
      reasons[day] = 'calendar_incomplete';
      if (!warnings.includes('calendar_incomplete')) warnings.push('calendar_incomplete');
    } else if (current.conflictDays.has(day)) {
      counts[day] = null;
      reasons[day] = 'duplicate_names';
    }
  }

  // ФИО используется только в памяти скрипта для объединения строк и месяцев.
  for (const [person, marks] of current.people) {
    const priorMarks = previous && previous.people.get(person);
    const initial = priorMarks ? previousState_(priorMarks) : {departed: false, uncertain: true};
    let departed = initial.departed;
    let uncertain = initial.uncertain;
    for (let day = 0; day < days; day++) {
      if (!current.available[day]) continue;
      const mark = marks[day];
      if (mark === '?') {
        departed = false;
        uncertain = true;
      } else if (isActive_(mark)) {
        departed = false;
        uncertain = false;
      } else if (mark === 'УБ') {
        departed = true;
        uncertain = false;
      } else if (isDeparture_(mark) && !departed) {
        if (uncertain && counts[day] !== null) {
          counts[day] = null;
          reasons[day] = 'previous_month_missing';
          if (!warnings.includes('previous_month_missing')) warnings.push('previous_month_missing');
        } else if (counts[day] !== null) {
          counts[day]++;
        }
        departed = true;
      }
    }
  }
  return {name, counts, reasons, warnings};
}

function buildPlannedDepartures_(year, month) {
  if (!Number.isInteger(year) || year < 2020 || year > 2099 ||
      !Number.isInteger(month) || month < 1 || month > 12) {
    throw new Error('Некорректный месяц');
  }
  const period = year + '-' + String(month).padStart(2, '0');
  return {month: period, objects: DEPARTURE_SOURCES.map(source => summarizeSource_(source, year, month))};
}

// Безопасная проверка: только агрегаты в журнал, никаких запросов к Вектору.
function previewPlannedDepartures() {
  const period = Utilities.formatDate(new Date(), 'Europe/Moscow', 'yyyy-MM');
  const payload = buildPlannedDepartures_(Number(period.slice(0, 4)), Number(period.slice(5, 7)));
  for (const object of payload.objects) {
    const total = object.counts.reduce((sum, count) => sum + (count || 0), 0);
    console.log(object.name + ': ' + total + ', нет данных за ' +
      object.counts.filter(count => count === null).length + ' дней; ' + object.warnings.join(', '));
  }
}

// Не запускать до настройки адреса и ключа и отдельной проверки сводки.
function sendPlannedDepartures() {
  const properties = PropertiesService.getScriptProperties();
  const url = properties.getProperty('VECTOR_IMPORT_URL');
  const key = properties.getProperty('VECTOR_IMPORT_KEY');
  if (!url || !/^https:\/\//.test(url) || !key || key.length < 32) {
    throw new Error('Настройте VECTOR_IMPORT_URL и VECTOR_IMPORT_KEY в свойствах скрипта');
  }
  const period = Utilities.formatDate(new Date(), 'Europe/Moscow', 'yyyy-MM');
  const payload = buildPlannedDepartures_(Number(period.slice(0, 4)), Number(period.slice(5, 7)));
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: {'X-Vector-Import-Key': key},
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
    validateHttpsCertificates: true,
  });
  if (response.getResponseCode() !== 200) {
    throw new Error('Вектор не принял сводку: HTTP ' + response.getResponseCode());
  }
  console.log('Передана обезличенная сводка за ' + payload.month +
    ': объектов ' + payload.objects.length);
}

// Вызывать только после успешной ручной проверки и первой отправки.
// Триггер работает от аккаунта владельца скрипта; веб-приложение не публикуется.
function enableHalfHourlyPlannedDepartures() {
  const exists = ScriptApp.getProjectTriggers().some(trigger =>
    trigger.getHandlerFunction() === 'sendPlannedDepartures');
  if (exists) {
    console.log('Обновление уже включено. Проверьте период существующего триггера в разделе «Триггеры»');
    return;
  }
  ScriptApp.newTrigger('sendPlannedDepartures').timeBased().everyMinutes(30).create();
  console.log('Обновление каждые 30 минут включено');
}

