"""Без сети, конфигурации приложения и реального ожидания."""
import ast
import logging
from pathlib import Path
from threading import local, Lock
import unittest
from unittest.mock import MagicMock


def client(payloads):
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'uis_api.py').read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
    ns = dict(UIS_BASE_URL='https://example.invalid', UIS_SYSTEMS={}, local=local,
              logger=logging.getLogger('test'), UIS_CALL_FIELDS=[],
              _wait_for_uis_slot=MagicMock(), _pause_uis_requests=MagicMock())
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<uis>', 'exec'), ns)
    ns['_wait_for_uis_slot'] = MagicMock()
    ns['_pause_uis_requests'] = MagicMock()
    api = ns['UISAPI']()
    session = MagicMock()
    session.post.side_effect = [MagicMock(status_code=200, json=MagicMock(return_value=p)) for p in payloads]
    api._get_session = lambda: session
    return api, session, ns


class UISLimitTests(unittest.TestCase):
    def test_retry_same_page_without_duplicate_rows(self):
        page = [{'id': i} for i in range(1000)]
        api, session, ns = client([
            {'result': {'data': page}},
            {'error': {'message': 'Limit per minute has been exceeded'}},
            {'result': {'data': [{'id': 1000}]}},
        ])
        progress = MagicMock()
        rows = api._fetch_calls('test', 'dummy', 'from', 'to', on_wait=progress)
        self.assertEqual(len(rows), 1001)
        self.assertEqual([c.kwargs['json']['params']['offset'] for c in session.post.call_args_list], [0, 1000, 1000])
        ns['_pause_uis_requests'].assert_called_once()
        progress.assert_called_once()

    def test_minute_retries_are_bounded(self):
        api, session, ns = client([{'error': {'message': 'Limit per minute has been exceeded'}}] * 3)
        with self.assertRaises(ns['UISLimitError']):
            api._fetch_calls('test', 'dummy', 'from', 'to')
        self.assertEqual(session.post.call_count, 3)

    def test_daily_limit_is_not_retried(self):
        api, session, ns = client([{'error': {'message': 'Limit per day has been exceeded'}}])
        with self.assertRaisesRegex(ns['UISLimitError'], 'суточный'):
            api._fetch_calls('test', 'dummy', 'from', 'to')
        self.assertEqual(session.post.call_count, 1)

    def test_limiter_spaces_requests_and_cooldown(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'uis_api.py').read_text(encoding='utf-8'))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('_wait_for_uis_slot', '_pause_uis_requests')]
        clock = [100.0]
        waits = []
        def sleep(seconds):
            waits.append(seconds)
            clock[0] += seconds
        ns = dict(_request_lock=Lock(), _next_request_at=0, monotonic=lambda: clock[0], sleep=sleep)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), '<limiter>', 'exec'), ns)
        ns['_wait_for_uis_slot']()
        ns['_wait_for_uis_slot']()
        ns['_pause_uis_requests']()
        ns['_wait_for_uis_slot']()
        self.assertAlmostEqual(waits[0], 1.1)
        self.assertAlmostEqual(waits[1], 61)
