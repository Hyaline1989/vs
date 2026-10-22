const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'integrations', 'planned_departures.gs'), 'utf8');
const createdTriggers = [];
const context = {
    ScriptApp: {
        getProjectTriggers: () => createdTriggers,
        newTrigger(handler) {
            assert.equal(handler, 'sendPlannedDepartures');
            return {
                timeBased() { return this; },
                everyMinutes(minutes) {
                    assert.equal(minutes, 30);
                    return this;
                },
                create() { createdTriggers.push({getHandlerFunction: () => handler}); },
            };
        },
    },
    console: {log() {}},
};
vm.runInNewContext(source + '\nthis.api = {locateCalendar_, readPeople_, chooseMonthSheet_, previousState_, summarizeSource_, enableHalfHourlyPlannedDepartures};', context);

function sheet(rows) {
    return {
        getMaxRows: () => rows.length,
        getMaxColumns: () => rows[0].length,
        getLastRow: () => rows.length,
        getRange(startRow, startCol, height, width) {
            return {
                getDisplayValues: () => Array.from({length: height}, (_, row) =>
                    Array.from({length: width}, (_, col) => rows[startRow - 1 + row]?.[startCol - 1 + col] ?? '')),
            };
        },
    };
}

const header = Array(14).fill('');
header[1] = 'ФИО';
header[11] = '1';
header[12] = '2';
header[13] = '3';
function person(day1, day2) {
    const row = Array(14).fill('');
    row[1] = 'Иванов Иван';
    row[11] = day1;
    row[12] = day2;
    return row;
}

const compatible = context.api.readPeople_(sheet([header, person('8', 'ОВ'), person('10', 'ОВ')]), 3, {});
assert.equal(compatible.conflictDays.size, 0);
assert.equal(compatible.people.size, 1);

const nextShift = context.api.readPeople_(sheet([header, person('8', 'ОВ'), person('ОВ', 'ОВ')]), 3, {});
assert.equal(nextShift.conflictDays.size, 0);
assert.equal(nextShift.people.get('ИВАНОВ ИВАН')[0], '8');

const reverseShift = context.api.readPeople_(sheet([header, person('ОВ', ''), person('11', '')]), 3, {});
assert.equal(reverseShift.conflictDays.size, 0);
assert.equal(reverseShift.people.get('ИВАНОВ ИВАН')[0], '11');

const acrossSheets = context.api.readPeople_([
    sheet([header, person('ОВ', '11')]),
    sheet([header, person('8', 'ОВ')]),
    sheet([header, person('11', '')]),
], 3, {});
assert.equal(acrossSheets.people.size, 1, 'Один человек на трёх листах учитывается один раз');
assert.equal(acrossSheets.conflictDays.size, 0);
assert.equal(acrossSheets.people.get('ИВАНОВ ИВАН')[0], '11');
assert.equal(acrossSheets.people.get('ИВАНОВ ИВАН')[1], '11');

const dayOff = context.api.readPeople_(sheet([header, person('ОВ', ''), person('В', '')]), 3, {});
assert.equal(dayOff.conflictDays.size, 0);
assert.equal(dayOff.people.get('ИВАНОВ ИВАН')[0], 'В');

const reverseDayOff = context.api.readPeople_(sheet([header, person('В', ''), person('ОВ', '')]), 3, {});
assert.equal(reverseDayOff.conflictDays.size, 0);
assert.equal(reverseDayOff.people.get('ИВАНОВ ИВАН')[0], 'В');
assert.equal(context.api.previousState_(['ОВ', 'В']).departed, false);

const voluntary = context.api.readPeople_(sheet([header, person('УБ', ''), person('ОВ', '')]), 3, {});
assert.equal(voluntary.conflictDays.size, 0);
assert.equal(voluntary.people.get('ИВАНОВ ИВАН')[0], 'УБ');
assert.equal(context.api.previousState_(['УБ']).departed, true);

const reverseVoluntary = context.api.readPeople_(sheet([header, person('ОВ', ''), person('УБ', '')]), 3, {});
assert.equal(reverseVoluntary.conflictDays.size, 0);
assert.equal(reverseVoluntary.people.get('ИВАНОВ ИВАН')[0], 'УБ');

const ambiguous = context.api.readPeople_(sheet([header, person('ОВ', ''), person('З', '')]), 3, {});
assert.equal(ambiguous.conflictDays.has(0), true);
assert.equal(ambiguous.people.get('ИВАНОВ ИВАН')[0], '?');

const numberedHeader = Array(41).fill('');
for (let day = 1; day <= 23; day++) numberedHeader[day] = String(day);
const actualCalendar = Array(41).fill('');
actualCalendar[1] = 'ФИО';
for (let day = 1; day <= 31; day++) actualCalendar[day + 9] = String(day);
const laterDeparture = Array(41).fill('');
laterDeparture[1] = 'Иванов Иван';
laterDeparture[40] = 'ОВ';
const twoRowHeader = context.api.readPeople_(
    sheet([numberedHeader, actualCalendar, laterDeparture]), 31, {});
const twoRowLayout = context.api.locateCalendar_(
    sheet([numberedHeader, actualCalendar, laterDeparture]), 31, {});
assert.equal(twoRowLayout.dayCol, 11);
assert.equal(twoRowLayout.firstDataRow, 3);
assert.equal(twoRowLayout.available.every(Boolean), true);
assert.equal(twoRowHeader.people.get('ИВАНОВ ИВАН')[30], 'ОВ');

const calendar = {getSheets: () => [
    {getName: () => 'Март 2026'},
    {getName: () => 'Май'},
]};
assert.equal(context.api.chooseMonthSheet_(calendar, 2026, 5).sheet.getName(), 'Май');
assert.equal(context.api.chooseMonthSheet_(calendar, 2027, 5).warning, 'sheet_missing');
assert.equal(context.api.previousState_(['ОВ', 'ОВ']).departed, true);

function monthSheet(name, days, people) {
    const columns = Array(32).fill('');
    columns[0] = 'ФИО';
    for (let day = 1; day <= days; day++) columns[day] = String(day);
    const rows = [columns, ...people.map(([personName, marks]) => {
        const row = Array(32).fill('');
        row[0] = personName;
        for (const [day, mark] of Object.entries(marks)) row[Number(day)] = mark;
        return row;
    })];
    return {...sheet(rows), getName: () => name};
}
const october = monthSheet('Октябрь 2026', 31, [
    ['Иванов Иван', {2: 'ОВ'}],
    ['Иванов Иван', {2: '11'}],
    ['Петрова Анна', {8: 'УБ'}],
    ['Петрова Анна', {8: 'ОВ'}],
    ['Волкова Татьяна', {15: 'ОВ'}],
    ['Волкова Татьяна', {15: 'В'}],
    ['Сидоров Пётр', {5: 'ОВ'}],
]);
const september = monthSheet('Сентябрь 2026', 30, [
    ['Иванов Иван', {30: '11'}],
    ['Петрова Анна', {30: '11'}],
    ['Волкова Татьяна', {30: '11'}],
    ['Сидоров Пётр', {30: '11'}],
]);
context.SpreadsheetApp = {openById: () => ({getSheets: () => [october, september]})};
const summary = context.api.summarizeSource_(['Тест', 'available'], 2026, 10);
assert.equal(summary.counts[1], 0); // ОВ + смена: перевахтовка.
assert.equal(summary.counts[7], 0); // УБ + ОВ: убытие не по плану.
assert.equal(summary.counts[14], 0); // ОВ + В: выходной на следующей вахте.
assert.equal(summary.counts[4], 1); // Одно ОВ: плановое убытие.
assert.equal(summary.warnings.length, 0);

context.SpreadsheetApp = {openById() { throw new Error('Недоступно'); }};
const missingSource = context.api.summarizeSource_(['Тест', 'no-access'], 2026, 10);
assert.equal(missingSource.counts.length, 31);
assert.equal(missingSource.reasons.length, 31);
assert.equal(missingSource.reasons[0], 'source_unavailable');

context.api.enableHalfHourlyPlannedDepartures();
context.api.enableHalfHourlyPlannedDepartures();
assert.equal(createdTriggers.length, 1);

console.log('Проверки Google-скрипта пройдены');

const namedBook = names => ({getSheets: () => names.map(name => ({getName: () => name}))});
const shiftNames = (month, year) => [
    `${month} ББ ${year} с 15:00`, `${month} ББ ${year} с 08:00`, `${month} КРС ${year}`,
];
const auto = {mergeMiratorgShifts: true};
const novemberNames = shiftNames('Ноябрь', 2026);
const mixedBook = namedBook([
    ...shiftNames('Октябрь', 2026), ...novemberNames,
    ...shiftNames('Ноябрь', 2027), 'Копия Ноябрь ББ 2026 с 15:00',
    'Ноябрь КРС 2026 архив', 'Ноябрь 2026',
]);
assert.deepEqual(Array.from(context.api.chooseMonthSheet_(mixedBook, 2026, 11, auto).sheet,
    part => part.getName()), novemberNames);
assert.equal(context.api.chooseMonthSheet_(mixedBook, 2027, 11, auto).sheet.length, 3);
assert.equal(context.api.chooseMonthSheet_(namedBook(novemberNames.slice(0, 2)), 2026, 11, auto).warning,
    'sheet_missing');
assert.equal(context.api.chooseMonthSheet_(namedBook(['Сентябрь 2026']), 2026, 9, auto).sheet.getName(),
    'Сентябрь 2026');
assert.equal(context.api.chooseMonthSheet_(namedBook(['Копия Ноябрь КРС 2026']), 2026, 11, auto).warning,
    'sheet_missing');
assert.equal(context.api.chooseMonthSheet_(namedBook(novemberNames), 2026, 11).warning,
    'sheet_ambiguous', 'Другие объекты не получают автоматическое объединение');
const yearlessBook = namedBook(shiftNames('Ноябрь', '').map(name => name.replace(/\s+/g, ' ')));
assert.equal(context.api.chooseMonthSheet_(yearlessBook, 2026, 11, auto).sheet.length, 3);
assert.equal(context.api.chooseMonthSheet_(yearlessBook, 2027, 11, auto).warning, 'sheet_missing');
console.log('Автоматический выбор смен по месяцу и году проверен');
