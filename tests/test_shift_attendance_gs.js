const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = ['planned_departures.gs', 'shift_attendance.gs']
    .map(name => fs.readFileSync(path.join(__dirname, '..', 'integrations', name), 'utf8'))
    .join('\n');
const context = {console: {log() {}}, SpreadsheetApp: {openById() { throw new Error('not set'); }}};
vm.runInNewContext(source + '\nthis.api = {summarizeShiftAttendanceSource_};', context);

function sheet(rows) {
    return {
        getName: () => 'Октябрь 2026',
        getMaxRows: () => rows.length,
        getMaxColumns: () => rows[0].length,
        getLastRow: () => rows.length,
        getRange(startRow, startCol, height, width) {
            return {getDisplayValues: () => Array.from({length: height}, (_, row) =>
                Array.from({length: width}, (_, col) => rows[startRow - 1 + row]?.[startCol - 1 + col] ?? ''))};
        },
    };
}

const header = Array(35).fill('');
header[0] = 'ФИО';
for (let day = 1; day <= 30; day++) header[day] = String(day);
const row = (name, day1, day2) => {
    const values = Array(35).fill('');
    values[0] = name;
    values[1] = day1;
    values[2] = day2;
    return values;
};
const current = sheet([
    header,
    row('Иванов Иван', '11', 'ОВ'),
    row('Иванов Иван', 'ОВ', '8'),
    row('Петров Пётр', '', 'В'),
]);
context.SpreadsheetApp.openById = () => ({getSheets: () => [current]});
const report = context.api.summarizeShiftAttendanceSource_(['Объект', 'id'], 2026, 10);
assert.equal(report.counts[0], 1, 'Повтор одного человека не удваивает смену');
assert.equal(report.counts[1], 1, 'Числовая смена важнее ОВ в другой строке');
assert.equal(report.counts[2], 0, 'Пустой день существующего листа равен нулю');
assert.equal(report.counts[30], null, 'Дата без колонки в шапке не равна нулю');
assert.equal(report.reasons[30], 'calendar_incomplete');

context.SpreadsheetApp.openById = () => ({getSheets: () => []});
const missing = context.api.summarizeShiftAttendanceSource_(['Объект', 'id'], 2026, 10);
assert.equal(missing.counts[0], null);
assert.equal(missing.reasons[0], 'sheet_missing');

const parts = [
    sheet([header, row('Иванов Иван', '11', 'ОВ')]),
    sheet([header, row('Иванов Иван', '8', '11')]),
    sheet([header, row('Петров Пётр', '11', '')]),
];
parts.forEach((part, index) => { part.getName = () => `Октябрь смена ${index}`; });
context.SpreadsheetApp.openById = () => ({getSheets: () => parts});
const override = {monthSheets: {'2026-10': parts.map(part => part.getName())}};
const combined = context.api.summarizeShiftAttendanceSource_(['Объект', 'id', override], 2026, 10);
assert.equal(combined.counts[0], 2, 'Листы объединяются, дубли не удваивают смены');
assert.equal(combined.counts[1], 1, 'Смена на другом листе учитывается');
assert.equal(combined.counts[30], null, 'Неполный календарь не становится нулём');
const ordinary = context.api.summarizeShiftAttendanceSource_(['Другой объект', 'id'], 2026, 10);
assert.equal(ordinary.reasons[0], 'sheet_ambiguous', 'Без настройки сохраняется прежнее поведение');
