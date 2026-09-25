# uis_api.py
# -*- coding: utf-8 -*-
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from threading import local

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from config import UIS_BASE_URL, UIS_SYSTEMS

logger = logging.getLogger(__name__)

UIS_CALL_FIELDS = [
    'id',
    'start_time',
    'finish_time',
    'direction',
    'employees',
    'clean_talk_duration',
    'total_duration',
    'finish_reason',
    'source'
]


class UISAPI:
    """Клиент UIS/CoMagic Data API для отчётов по звонкам."""

    def __init__(self, base_url=UIS_BASE_URL, systems=None):
        self.base_url = base_url.rstrip('/')
        self.systems = systems or UIS_SYSTEMS
        self._daily_call_counts = {}
        self._session_local = local()

    def _get_session(self):
        session = getattr(self._session_local, 'session', None)
        if session is None:
            session = requests.Session()
            retries = Retry(
                total=2,
                connect=2,
                read=0,
                status=0,
                backoff_factor=0.5,
                allowed_methods={'POST'},
            )
            session.mount('https://', HTTPAdapter(max_retries=retries))
            self._session_local.session = session
        return session

    def get_calls_for_date(self, date_str):
        start = f'{date_str} 00:00:00'
        finish = f'{date_str} 23:59:59'
        rows = []

        for system_name, access_token in self.systems.items():
            if not access_token:
                logger.warning(f'UIS API key is not configured for {system_name}')
                continue

            calls = self._fetch_calls(system_name, access_token, start, finish)
            rows.extend(self._normalize_calls(system_name, calls))

        return rows

    def get_calls_for_period(self, date_from, date_till):
        """Звонки за включительный период небольшими порциями для UIS."""
        rows = []
        first = datetime.strptime(date_from, '%Y-%m-%d').date()
        last = datetime.strptime(date_till, '%Y-%m-%d').date()
        for system_name, access_token in self.systems.items():
            if access_token:
                current = first
                while current <= last:
                    chunk_end = min(current + timedelta(days=6), last)
                    calls = self._fetch_calls_split_on_timeout(system_name, access_token, current, chunk_end)
                    rows.extend(self._normalize_calls(system_name, calls))
                    current = chunk_end + timedelta(days=1)
        return rows

    def get_call_counts_for_period(self, date_from, date_till, progress=None):
        """Месячные счётчики звонков без хранения всех звонков в отчёте."""
        first = datetime.strptime(date_from, '%Y-%m-%d').date()
        last = min(datetime.strptime(date_till, '%Y-%m-%d').date(), datetime.now().date())
        totals = defaultdict(int)
        days = (last - first).days + 1
        for system_name, access_token in self.systems.items():
            if not access_token:
                continue
            for index in range(max(days, 0)):
                day = first + timedelta(days=index)
                cache_key = (system_name, day.isoformat())
                if progress:
                    progress(system_name, day.isoformat(), index + 1, days)
                if cache_key not in self._daily_call_counts or day == datetime.now().date():
                    calls = self._fetch_calls(
                        system_name, access_token,
                        f'{day.isoformat()} 00:00:00', f'{day.isoformat()} 23:59:59'
                    )
                    day_counts = defaultdict(int)
                    for row in self._normalize_calls(system_name, calls):
                        direction = row['direction']
                        duration = row['clean_talk_duration']
                        if (direction == 'in' and row['is_talked'] and duration > 0) or direction == 'out':
                            day_counts[row['employee_name']] += 1
                    self._daily_call_counts[cache_key] = dict(day_counts)
                for employee_name, count in self._daily_call_counts[cache_key].items():
                    totals[(system_name, employee_name)] += count
        return [
            {'system': system, 'employee_name': name, 'count': count}
            for (system, name), count in totals.items()
        ]

    def _fetch_calls_split_on_timeout(self, system_name, access_token, first, last):
        try:
            return self._fetch_calls(
                system_name, access_token,
                f'{first.isoformat()} 00:00:00',
                f'{last.isoformat()} 23:59:59'
            )
        except requests.exceptions.Timeout:
            if first == last:
                raise
            middle = first + timedelta(days=(last - first).days // 2)
            logger.warning('UIS timeout за %s—%s; делим период', first, last)
            return (
                self._fetch_calls_split_on_timeout(system_name, access_token, first, middle)
                + self._fetch_calls_split_on_timeout(system_name, access_token, middle + timedelta(days=1), last)
            )

    def _fetch_calls(self, system_name, access_token, date_from, date_till):
        result = []
        limit = 1000
        offset = 0

        while True:
            payload = {
                'jsonrpc': '2.0',
                'id': f'calls-{system_name}-{offset}',
                'method': 'get.calls_report',
                'params': {
                    'access_token': access_token,
                    'date_from': date_from,
                    'date_till': date_till,
                    'limit': limit,
                    'offset': offset,
                    'fields': UIS_CALL_FIELDS,
                    'sort': [{'field': 'start_time', 'order': 'asc'}]
                }
            }

            response = self._get_session().post(self.base_url, json=payload, timeout=(5, 40))
            response.raise_for_status()
            data = response.json()

            if data.get('error'):
                raise RuntimeError(data['error'].get('message') or str(data['error']))

            batch = data.get('result', {}).get('data') or []
            result.extend(batch)

            if len(batch) < limit:
                break
            offset += limit

        return result

    def _normalize_calls(self, system_name, calls):
        rows = []
        for call in calls:
            employees = call.get('employees') or []
            if not employees:
                rows.append(self._normalize_call_row(system_name, call, None))
                continue

            for employee in employees:
                rows.append(self._normalize_call_row(system_name, call, employee))

        return rows

    def _normalize_call_row(self, system_name, call, employee):
        employee = employee or {}
        start_time = self._normalize_datetime(call.get('start_time'))
        finish_time = self._normalize_datetime(call.get('finish_time'))
        employee_name = (
            employee.get('employee_full_name')
            or employee.get('full_name')
            or employee.get('name')
            or ''
        )

        return {
            'system': system_name,
            'id': str(call.get('id') or ''),
            'start_time': start_time,
            'finish_time': finish_time,
            'direction': call.get('direction') or '',
            'employee_name': employee_name,
            'is_talked': bool(employee.get('is_talked', False)),
            'clean_talk_duration': int(call.get('clean_talk_duration') or employee.get('clean_talk_duration') or 0),
            'total_duration': int(call.get('total_duration') or 0),
            'finish_reason': call.get('finish_reason') or '',
            'source': call.get('source') or ''
        }

    @staticmethod
    def _normalize_datetime(value):
        if not value:
            return ''
        value = str(value).replace('T', ' ')
        if '+' in value:
            value = value.split('+', 1)[0]
        return value[:19]


def validate_report_date(date_str):
    datetime.strptime(date_str, '%Y-%m-%d')
    return date_str
