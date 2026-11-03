"""Классификация входящих только для дневного отчёта по звонкам."""
BLOCK_ROUTE = ('Распределение по данным из CRM 1', 'Переадресация 5', 'Информационное сообщение 3')


def report_calls(api, system, calls):
    rows, seen = [], set()
    for call in calls:
        key = str(call.get('id') or '')
        if not key:
            raise ValueError('UIS вернул звонок без ID; точный подсчёт невозможен')
        if key in seen:
            continue
        seen.add(key)
        if call.get('direction') != 'in':
            rows.extend(api._normalize_calls(system, [call]))
            continue
        names = tuple(op.get('name') for op in (call.get('scenario_operations') or []))
        reason = call.get('finish_reason')
        if reason == 'numa_in_black_list':
            category = 'blocked_old'
        elif names == BLOCK_ROUTE:
            category = 'blocked_new'
        elif call.get('is_lost') is False:
            category = 'accepted'
        elif reason in ('subscriber_disconnects', 'no_success_operator_call'):
            category = 'missed'
        else:
            category = 'technical'
        employees = call.get('employees') or []
        candidates = employees
        if category == 'accepted':
            first = call.get('first_talked_employee_id')
            candidates = [e for e in employees if first is not None and str(e.get('employee_id')) == str(first)]
            if not candidates:
                candidates = [e for e in employees if e.get('is_talked')]
        unique = {str(e.get('employee_id') or e.get('employee_full_name') or e.get('full_name') or e.get('name')): e for e in candidates}
        employee = next(iter(unique.values())) if len(unique) == 1 else None
        row = api._normalize_call_row(system, call, employee)
        row['incoming_category'] = category
        row['company_unassigned'] = employee is None
        if employee is None:
            row['employee_name'] = 'Без однозначного назначения'
        if category == 'accepted':
            row['is_talked'] = True
        rows.append(row)
    return rows


def incoming_summary(rows):
    counts = dict(accepted=0, missed=0, technical=0, blocked_old=0, blocked_new=0)
    seen = set()
    for row in rows:
        key = (row.get('system'), row.get('id'))
        category = row.get('incoming_category')
        if category in counts and key not in seen:
            counts[category] += 1
            seen.add(key)
    return counts
