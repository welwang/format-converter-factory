"""驗證驗收閘門會拒絕缺檔、共同失敗、漏通知及錯誤程序狀態。"""
import contextlib
import copy
import io
import json
import pathlib
import tempfile
import unittest

import gate_compare as compare
import gate_engine as engine


def engine_report():
    job = {'id': 'x1234', 'state': 'done', 'target': 'm4a', 'created': 1, 'elapsed': 1}
    cancelled = dict(job, state='cancelled', output='a.flac', encoder='flac')
    return {'records': [
        {'case': 'describe', 'result': []}, {'case': 'media_info', 'result': {}},
        {'case': 'start_audio', 'accepted': 1},
        {'case': 'finish_audio', 'result': [copy.deepcopy(job)]},
        {'case': 'finish_fastcopy', 'result': [copy.deepcopy(job)]},
        {'case': 'cancel_reply', 'result': True},
        {'case': 'cancel_state', 'result': [cancelled]},
        {'case': 'unknown_method', 'result': None},
        {'case': 'clear', 'result': True}, {'case': 'quit', 'result': True}]}


def shell_report():
    return {'exit_code': 0, 'report': {'_swbd_smoke': True, 'ok': True, 'preview': True,
            'error_rejection': True, 'formats': 10, 'mixed_jobs': 2, 'completion_notifications': 1}}


class GateGuards(unittest.TestCase):
    def compare(self, a, b):
        with tempfile.TemporaryDirectory(dir=pathlib.Path(__file__).parent) as directory, contextlib.redirect_stdout(io.StringIO()):
            root = pathlib.Path(directory)
            for name, obj in [('a.json', a), ('b.json', b)]:
                if obj is not None:
                    (root / name).write_text(json.dumps(obj), encoding='utf-8')
            return compare.compare('test', root / 'a.json', root / 'b.json')

    def test_missing_report_fails(self):
        self.assertFalse(self.compare(None, engine_report()))

    def test_both_missing_fail(self):
        self.assertFalse(self.compare(None, None))

    def test_matching_engine_failures_fail(self):
        report = engine_report()
        report['records'][4]['result'][0]['state'] = 'error'
        self.assertFalse(self.compare(report, copy.deepcopy(report)))

    def test_missing_case_fails(self):
        report = engine_report()
        report['records'].pop()
        self.assertFalse(self.compare(report, report))

    def test_dynamic_job_time_and_id_allowed(self):
        a, b = engine_report(), engine_report()
        b['records'][3]['result'][0].update(id='x9876', created=9, elapsed=9)
        self.assertTrue(self.compare(a, b))

    def test_cancel_race_fields_allowed(self):
        a, b = engine_report(), engine_report()
        b['records'][6]['result'][0].update(output='', encoder='')
        self.assertTrue(self.compare(a, b))

    def test_arbitrary_token_not_ignored(self):
        a, b = engine_report(), engine_report()
        a['token'], b['token'] = 'a', 'b'
        self.assertFalse(self.compare(a, b))

    def test_non_job_elapsed_not_ignored(self):
        a, b = engine_report(), engine_report()
        a['elapsed'], b['elapsed'] = 1, 2
        self.assertFalse(self.compare(a, b))

    def test_positive_notification_counts_allowed(self):
        a, b = shell_report(), shell_report()
        b['report']['completion_notifications'] = 3
        self.assertTrue(self.compare(a, b))

    def test_no_notification_fails(self):
        report = shell_report()
        report['report']['completion_notifications'] = 0
        self.assertFalse(self.compare(report, report))

    def test_matching_shell_failures_fail(self):
        report = shell_report()
        report['report']['ok'] = False
        self.assertFalse(self.compare(report, report))

    def test_nonzero_exit_fails(self):
        report = shell_report()
        report['exit_code'] = 1
        self.assertFalse(self.compare(report, report))

    def test_conversion_output_must_exist_and_match_size(self):
        with tempfile.TemporaryDirectory(dir=pathlib.Path(__file__).parent) as directory:
            output = pathlib.Path(directory) / 'output.m4a'
            job = {'state': 'done', 'output': str(output), 'out_size': 3}
            with self.assertRaises(RuntimeError):
                engine.require_success('test', [job])
            output.write_bytes(b'abc')
            self.assertEqual(engine.require_success('test', [job]), [job])
            job['out_size'] = 4
            with self.assertRaises(RuntimeError):
                engine.require_success('test', [job])
            job['state'] = 'error'
            with self.assertRaises(RuntimeError):
                engine.require_success('test', [job])


if __name__ == '__main__':
    unittest.main()
