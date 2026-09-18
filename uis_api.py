# uis_api.py
# -*- coding: utf-8 -*-
import logging
from datetime import datetime

import requests

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

            response = requests.post(self.base_url, json=payload, timeout=40)
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
