"""Очередь запросов на пересчёт табелей без изменений SQLite-базы."""

import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from planned_departures_store import days_in_month


STORE_DIR = Path(__file__).resolve().parent / 'data' / 'report_refresh'
REPORTS = {'departures', 'shifts'}


def _path(report, month, store_dir):
    if report not in REPORTS:
        raise ValueError('Неизвестный отчёт')
    days_in_month(month)
    return Path(store_dir) / report / f'{month}.json'


@contextmanager
def _locked(store_dir):
    root = Path(store_dir)
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.lock').open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b'0')
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _read(path):
    try:
        with path.open(encoding='utf-8') as stream:
            return json.load(stream)
    except FileNotFoundError:
        return None


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix='.refresh-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != 'nt':
            os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def request_refresh(report, month, store_dir=STORE_DIR):
    path = _path(report, month, store_dir)
    with _locked(store_dir):
        existing = _read(path)
        now = datetime.now(timezone.utc)
        if existing and existing.get('status') == 'pending':
            created = datetime.fromisoformat(existing['requested_at'])
            if now - created < timedelta(minutes=20):
                return existing
        payload = {
            'id': uuid.uuid4().hex, 'report': report, 'month': month,
            'status': 'pending', 'requested_at': now.isoformat(timespec='seconds'),
            'updated_at': now.isoformat(timespec='seconds'),
            'next_attempt_at': now.isoformat(timespec='seconds'), 'attempts': 0,
        }
        _write(path, payload)
        return payload


def get_refresh(report, month, request_id, store_dir=STORE_DIR):
    path = _path(report, month, store_dir)
    payload = _read(path)
    return payload if payload and payload['id'] == request_id else None


def claim_pending(store_dir=STORE_DIR):
    with _locked(store_dir):
        now = datetime.now(timezone.utc)
        candidates = []
        for report in sorted(REPORTS):
            for path in (Path(store_dir) / report).glob('*.json'):
                payload = _read(path)
                if payload and payload.get('status') == 'pending':
                    candidates.append((payload['requested_at'], path, payload))
        for _, path, payload in sorted(candidates):
            if datetime.fromisoformat(payload['next_attempt_at']) > now:
                continue
            if payload['attempts'] >= 5:
                payload['status'] = 'error'
                payload['updated_at'] = now.isoformat(timespec='seconds')
                _write(path, payload)
                continue
            payload['attempts'] += 1
            payload['next_attempt_at'] = (now + timedelta(minutes=2)).isoformat(timespec='seconds')
            payload['updated_at'] = now.isoformat(timespec='seconds')
            _write(path, payload)
            return {key: payload[key] for key in ('id', 'report', 'month')}
    return None


def finish_refresh(report, month, request_id, status, store_dir=STORE_DIR):
    if status not in ('completed', 'error'):
        raise ValueError('Некорректный статус')
    path = _path(report, month, store_dir)
    with _locked(store_dir):
        payload = _read(path)
        if not payload or payload['id'] != request_id or payload['status'] != 'pending':
            return False
        payload['status'] = status
        payload['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        _write(path, payload)
        return True
