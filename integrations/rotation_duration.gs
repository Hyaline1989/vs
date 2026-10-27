// Добавить отдельным файлом в тот же Apps Script. Исходные табели не изменяются.
// ФИО остаются только в памяти Google. В Вектор передаются HMAC-коды и отметки.
// VECTOR_ROTATION_ID_KEY создаётся один раз. НЕ менять при ротации ключа импорта.
function rotationIdentityKey_() {
  const properties = PropertiesService.getScriptProperties();
  let key = properties.getProperty('VECTOR_ROTATION_ID_KEY');
  if (!key) {
    key = Utilities.getUuid() + Utilities.getUuid();
    properties.setProperty('VECTOR_ROTATION_ID_KEY', key);
  }
  return key;
}

function rotationHex_(bytes) {
  return bytes.map(b => (b & 255).toString(16).padStart(2, '0')).join('');
}

function rotationPersonId_(name, key) {
  const normalized = String(name).trim().replace(/\s+/g, ' ').toUpperCase().replace(/Ё/g, 'Е');
  return rotationHex_(Utilities.computeHmacSha256Signature('vector-rotation-v1:' + normalized, key));
}

function rotationCode_(value) {
  const mark = String(value).trim().toUpperCase();
  if (isWork_(mark)) return 'W';
  if (['В', 'Б', 'СТ', 'З', 'УБ', 'УВ', 'ОВ', 'П'].includes(mark)) return mark;
  return mark ? '?' : '';
}

function rotationSource_(source, year, month, key) {
  const [name, id, override = {}] = source;
  const days = monthDays_(year, month);
  const empty = reason => ({name, reason, available: Array(days).fill(false), people: []});
  let book;
  try { book = SpreadsheetApp.openById(id); }
  catch (_) { return empty('source_unavailable'); }
  let selected;
  try { selected = chooseMonthSheet_(book, year, month, override); }
  catch (_) { return empty('source_unavailable'); }
  if (!selected.sheet) return empty(selected.warning);
  const available = Array(days).fill(true), people = new Map();
  try {
    for (const sheet of (Array.isArray(selected.sheet) ? selected.sheet : [selected.sheet])) {
      const layout = locateCalendar_(sheet, days, override);
      if (!layout) return empty('layout_unknown');
      for (let d = 0; d < days; d++) available[d] = available[d] && layout.available[d];
      const lastRow = sheet.getLastRow();
      const width = Math.min(sheet.getMaxColumns(), Math.max(layout.dayCol + days - 1, 90));
      // Одно чтение значений и цветов вместо запросов для каждого человека.
      const range = sheet.getRange(1, 1, lastRow, width);
      const values = range.getDisplayValues(), colors = range.getBackgrounds();
      const foremanColors = new Set();
      for (let r = 0; r < values.length; r++) {
        for (let c = layout.dayCol - 1; c < width; c++) {
          if (/бри?гад/i.test(values[r][c]) && c > 0 && isWork_(String(values[r][c - 1]).trim())) {
            foremanColors.add(colors[r][c - 1]);
          }
        }
      }
      for (let r = layout.firstDataRow - 1; r < values.length; r++) {
        const fullname = values[r][layout.nameCol - 1];
        if (!looksLikePerson_(fullname) || /\d/.test(fullname) ||
            /^(ВСЕГО|КОЛИЧЕСТВО|ОСВОБОЖДЕН|РАБОЧИЙ БРИГАДИР)/i.test(String(fullname).trim())) continue;
        const pid = rotationPersonId_(fullname, key);
        if (!people.has(pid)) people.set(pid, {id: pid, excluded: false, marks: Array.from({length: days}, () => [])});
        const person = people.get(pid);
        if (values[r].slice(0, layout.dayCol - 1).some(v => /бри?гад|менеджер|\bАУП\b/i.test(v) || String(v).trim().toUpperCase() === 'АУП')) {
          person.excluded = true;
        }
        for (let d = 0; d < days; d++) {
          if (!layout.available[d]) continue;
          const c = layout.dayCol - 1 + d;
          const code = rotationCode_(values[r][c]);
          if (code === 'W' && foremanColors.has(colors[r][c])) person.excluded = true;
          if (code && !person.marks[d].includes(code)) person.marks[d].push(code);
        }
      }
    }
  } catch (_) { return empty('source_unavailable'); }
  return {name, reason: null, available, people: [...people.values()]};
}

function sendRotationPart_(task, base, importKey) {
  const index = task.cursor;
  if (!Number.isInteger(index) || index < 0 || index >= DEPARTURE_SOURCES.length) throw new Error('Некорректный номер табеля');
  const secret = rotationIdentityKey_();
  const payload = {
    month: task.month, batch_id: task.id, cursor: index,
    key_id: rotationHex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, secret)),
    expected_objects: DEPARTURE_SOURCES.map(s => s[0]),
    object: rotationSource_(DEPARTURE_SOURCES[index], Number(task.month.slice(0, 4)), Number(task.month.slice(5, 7)), secret),
  };
  const response = UrlFetchApp.fetch(base + '/api/service/rotations/import', {
    method: 'post', contentType: 'application/json',
    headers: {'X-Vector-Import-Key': importKey},
    payload: JSON.stringify(payload), muteHttpExceptions: true,
  });
  if (response.getResponseCode() !== 200) throw new Error('Импорт продолжительности: HTTP ' + response.getResponseCode());
  console.log('Продолжительность: ' + task.month + ', табель ' + (index + 1) + '/' + DEPARTURE_SOURCES.length);
}
