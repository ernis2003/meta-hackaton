from contextlib import closing
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from test_auth import app
from src.database.connection import connect
from src.database import get_db
from src.forensics import build_results, graph
from src.pcap_analysis import inspect_runtime, read_logs, PCAP_MAGIC
from src.analyses import baseline_for
from src.database.migrations import migrate


def conn(uid='C1', ts=100, **values):
    return dict(uid=uid, ts=ts, **{'id.orig_h': '10.0.0.1', 'id.resp_h': '10.0.0.2',
                'id.orig_p': 50000, 'id.resp_p': 443, 'proto': 'tcp',
                'orig_ip_bytes': 100, 'resp_ip_bytes': 200, **values})


class EvidenceTests(unittest.TestCase):
    def test_uid_direction_aggregation_and_optional_logs(self):
        results = build_results({'conn': [conn(), conn('C2')],
            'ssl': [dict(uid='C1', server_name='example.org', ja4='actual-client', ja4s='actual-server')],
            'http': [dict(uid='C2', host='example.org', ja4h='actual-http')]})
        self.assertEqual(len(results['subjects']), 2)
        client = next(s for s in results['subjects'] if s['ip_address'] == '10.0.0.1')
        self.assertEqual(client['bytes_sent'], 200)
        self.assertEqual(client['unique_destinations'], 1)
        server_fp = next(f for f in results['fingerprints'] if f['type'] == 'ja4s')
        self.assertEqual(server_fp['hosts'], ['10.0.0.2'])
        relationships = results['relationships']
        communication = next(e for e in relationships if e['type'] == 'communicates_with')
        self.assertEqual(communication['metadata']['connection_count'], 2)
        self.assertEqual(communication['metadata']['total_bytes'], 600)
        self.assertEqual(len({e['id'] for e in relationships}), len(relationships))
        built = graph(*(results[k] for k in ('subjects', 'fingerprints', 'relationships', 'anomalies')))
        self.assertEqual(len(built['nodes']), 6)
        self.assertFalse(build_results({'conn': [conn()]})['fingerprints'])

    def test_dns_uses_answers_client_time_and_ttl_not_uid(self):
        logs = {'conn': [conn(ts=105), conn('late', ts=500)], 'dns': [dict(uid='unrelated',
            ts=100, query='example.org', answers=['10.0.0.2'], TTLs=[30], **{'id.orig_h': '10.0.0.1'})]}
        results = build_results(logs)
        self.assertEqual(results['connections'][0]['domains'], ['example.org'])
        self.assertEqual(results['connections'][1]['domains'], [])
        edge = next(e for e in results['relationships'] if e['type'] == 'connects_to_domain')
        self.assertEqual(edge['metadata']['connection_count'], 1)

    def test_ja3_is_not_ja4_and_unrelated_uid_is_ignored(self):
        results = build_results({'conn': [conn()], 'ssl': [dict(uid='C1', ja3='wrong'),
                                      dict(uid='other', ja4='unrelated')]})
        self.assertEqual(results['fingerprints'], [])

    def test_anomalies_and_historical_baseline(self):
        logs = {'conn': [conn(str(i), ts=i * 10) for i in range(6)]}
        results = build_results(logs)
        anomaly = results['anomalies'][0]
        self.assertEqual(anomaly['type'], 'periodic_communication')
        self.assertEqual(len(anomaly['connection_ids']), 6)
        self.assertEqual(results['subjects'][0]['risk_score'], 15)
        self.assertEqual(set(anomaly['subject_ids']), {s['id'] for s in results['subjects']})
        self.assertFalse(any(a['type'].startswith('new_') for a in results['anomalies']))
        baseline = dict(hosts={'10.0.0.1'}, pairs=set(), fingerprints=set(), count=1)
        logs['ssl'] = [dict(uid='0', ja4='observed')]
        results = build_results(logs, baseline)
        self.assertIn('new_destination', [a['type'] for a in results['anomalies']])
        self.assertIn('new_fingerprint', [a['type'] for a in results['anomalies']])

    def test_capability_probe_missing_runtime(self):
        with patch('src.pcap_analysis.subprocess.run', side_effect=FileNotFoundError()):
            self.assertEqual(inspect_runtime()['fingerprints']['ja4'], 'unavailable')

    def test_invalid_json_logs_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            for invalid in ('not JSON\n', '[]\n'):
                (path / 'conn.log').write_text(invalid)
                with self.assertRaises(HTTPException) as error:
                    read_logs(path)
                self.assertEqual(error.exception.status_code, 502)

    def test_null_optional_fields_do_not_break_statistics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'conn.log').write_text(json.dumps({'proto': None, 'service': None,
                'orig_pkts': None, 'orig_ip_bytes': None, 'id.orig_h': None}) + '\n')
            result = read_logs(path)
        self.assertEqual(result['summary']['packets'], 0)
        self.assertEqual(result['summary']['hosts'], [])
        self.assertEqual(result['summary']['protocols'], {'unknown': 1})

    def test_rolling_frequency_and_volume_rules(self):
        records = [conn(str(i), ts=i / 10) for i in range(101)]
        records.append(conn('later', ts=1000, orig_ip_bytes=110 * 1024 * 1024))
        results = build_results({'conn': records})
        kinds = {a['type'] for a in results['anomalies']}
        self.assertIn('frequent_connections', kinds)
        self.assertIn('high_traffic_volume', kinds)


class AnalysisAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbpatch = patch('src.database.connection.DATABASE_PATH', Path(self.tmp.name) / 'db.sqlite3')
        self.dbpatch.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = self.register('owner@example.org')
        self.other = self.register('other@example.org')

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.dbpatch.stop()
        self.tmp.cleanup()

    def register(self, email):
        response = self.client.post('/api/signup', json=dict(email=email, password='test-password', name='Test', surname='User'))
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    def test_history_with_connection_created_on_another_thread(self):
        # Create on the test thread, then authenticate/query/close via FastAPI's
        # worker threads instead of relying on incidental thread-pool reuse.
        with closing(connect()) as db:
            def database_from_another_thread():
                yield db
            app.dependency_overrides[get_db] = database_from_another_thread
            try:
                response = self.client.get('/api/analyses', headers=self.headers)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['total'], 0)
            finally:
                app.dependency_overrides.pop(get_db, None)

    def test_subject_activity_direction_buckets_and_authorization(self):
        def logs(directory):
            records = [conn('out', ts=100, duration=5),
                       conn('in', ts=120, **{'id.orig_h': '10.0.0.2', 'id.resp_h': '10.0.0.1'}),
                       conn('untimed', ts=None)]
            (directory / 'conn.log').write_text('\n'.join(json.dumps(c) for c in records))
        with patch('src.pcap_analysis.run_zeek', side_effect=logs), patch('src.analyses.inspect_runtime',
                   return_value=dict(fingerprints=dict(ja4='unsupported', ja4s='unsupported', ja4h='unsupported'))):
            response = self.upload()
        self.assertEqual(response.status_code, 201, response.text)
        aid = response.json()['id']
        path = f'/api/analyses/{aid}/activity/ip:10.0.0.1'
        response = self.client.get(path, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        activity = response.json()
        self.assertEqual(activity['total_connections'], 3)
        self.assertEqual(activity['untimed_connections'], 1)
        self.assertEqual(sum(b['sent'] for b in activity['buckets']), 300)
        self.assertEqual(sum(b['received'] for b in activity['buckets']), 300)
        self.assertEqual(sum(b['connections'] for b in activity['buckets']), 2)
        self.assertEqual(activity['peers'][0]['sent'], 400)
        self.assertEqual(activity['peers'][0]['received'], 500)
        self.assertEqual(activity['connections'][0]['subject_sent'], 200)
        self.assertEqual(activity['connections'][0]['peer'], '10.0.0.2')
        self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get(path, headers=self.other).status_code, 404)
        self.assertEqual(self.client.get(f'/api/analyses/{aid}/activity/ip:missing', headers=self.headers).status_code, 404)

    def fake_zeek(self, directory):
        with closing(connect()) as db:
            self.assertEqual(db.execute('SELECT status FROM analyses ORDER BY uploaded_at DESC').fetchone()[0], 'processing')
        (directory / 'conn.log').write_text(json.dumps(conn()) + '\n')
        (directory / 'ssl.log').write_text(json.dumps(dict(uid='C1', server_name='example.org')) + '\n')

    def upload(self, content=b'\xd4\xc3\xb2\xa1' + b'\0' * 20, filename='capture.pcap', route='/api/analyses'):
        return self.client.post(route, headers=self.headers, files={'file': (filename, content)})

    def test_pipeline_persistence_reopen_pagination_and_authorization(self):
        with patch('src.pcap_analysis.run_zeek', side_effect=self.fake_zeek), patch('src.analyses.inspect_runtime',
             return_value=dict(version='test', fingerprints=dict(ja4='unsupported', ja4s='unsupported', ja4h='unsupported'))):
            result = self.upload()
        self.assertEqual(result.status_code, 201, result.text)
        analysis = result.json()
        self.assertEqual(analysis['status'], 'completed')
        self.assertEqual([e['status'] for e in analysis['status_history']], ['pending', 'processing', 'completed'])
        self.assertEqual(analysis['summary']['connection_count'], 1)
        aid = analysis['id']
        with patch('src.pcap_analysis.run_zeek', side_effect=AssertionError('must not reprocess')):
            for suffix in ('', '/status', '/graph', '/subjects', '/connections', '/fingerprints', '/anomalies'):
                response = self.client.get('/api/analyses/' + aid + suffix, headers=self.headers)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(self.client.get('/api/analyses/' + aid + suffix, headers=self.other).status_code, 404)
                self.assertEqual(self.client.get('/api/analyses/' + aid + suffix).status_code, 401)
        self.assertEqual(self.client.get('/api/analyses', headers=self.other).json()['total'], 0)
        self.assertEqual(self.client.get('/api/analyses', headers=self.headers).json()['total'], 1)
        page = self.client.get(f'/api/analyses/{aid}/subjects?limit=1&offset=1', headers=self.headers).json()
        self.assertEqual(page['total'], 2)
        self.assertEqual(len(page['items']), 1)
        limited = self.client.get(f'/api/analyses/{aid}/graph?limit=1', headers=self.headers).json()
        self.assertTrue(limited['truncated'])
        self.assertEqual(len(limited['nodes']), 1)

    def test_invalid_empty_and_failed_status_persisted(self):
        with patch('src.pcap_analysis.run_zeek') as runtime:
            for content, filename in ((b'', 'empty.pcap'), (b'not pcap', 'invalid.pcap'), (b'bad', 'invalid.txt')):
                response = self.upload(content, filename)
                self.assertIn(response.status_code, (415, 422))
                aid = response.json()['detail']['analysis_id']
                self.assertEqual(self.client.get(f'/api/analyses/{aid}/status', headers=self.headers).json()['status'], 'failed')
                status = self.client.get(f'/api/analyses/{aid}', headers=self.headers).json()
                self.assertEqual([e['status'] for e in status['status_history']], ['pending', 'processing', 'failed'])
            runtime.assert_not_called()

    def test_zeek_failure_and_legacy_route_share_persistence(self):
        with patch('src.pcap_analysis.run_zeek', side_effect=HTTPException(503, 'Zeek unavailable')):
            result = self.upload(route='/api/pcap/analyze')
        self.assertEqual(result.status_code, 503)
        aid = result.json()['detail']['analysis_id']
        self.assertEqual(self.client.get(f'/api/analyses/{aid}', headers=self.headers).json()['error'], 'Zeek unavailable')

    def test_example_uses_real_pipeline_and_cannot_select_arbitrary_paths(self):
        self.assertEqual(self.client.get('/api/analyses/examples').status_code, 401)
        sample = Path(self.tmp.name) / 'example.pcap'
        sample.write_bytes(bytes.fromhex('d4c3b2a1020004000000000000000000ffff000001000000'))
        with patch('src.analyses.EXAMPLE', sample), patch('src.pcap_analysis.run_zeek', side_effect=self.fake_zeek), patch('src.analyses.inspect_runtime',
                   return_value=dict(fingerprints=dict(ja4='unsupported', ja4s='unsupported', ja4h='unsupported'))):
            example = self.client.get('/api/analyses/examples', headers=self.headers).json()['items'][0]
            result = self.client.post('/api/analyses/examples/' + example['id'], headers=self.headers)
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()['status'], 'completed')
        self.assertEqual(self.client.post('/api/analyses/examples/unknown.pcap', headers=self.headers).status_code, 404)

    def test_pipeline_does_not_truncate_connections_at_1000(self):
        def many(directory):
            (directory / 'conn.log').write_text('\n'.join(json.dumps(conn(str(i), ts=i)) for i in range(1005)))
        with patch('src.pcap_analysis.run_zeek', side_effect=many), patch('src.analyses.inspect_runtime',
                   return_value=dict(fingerprints=dict(ja4='unsupported', ja4s='unsupported', ja4h='unsupported'))):
            response = self.upload()
        self.assertEqual(response.status_code, 201, response.text)
        aid = response.json()['id']
        self.assertEqual(response.json()['summary']['connection_count'], 1005)
        page = self.client.get(f'/api/analyses/{aid}/connections', headers=self.headers).json()
        self.assertEqual(page['total'], 1005)
        indicators = self.client.get(f'/api/analyses/{aid}/anomalies?anomaly_type=periodic_communication&subject_id=ip:10.0.0.1', headers=self.headers).json()
        self.assertEqual(indicators['total'], 1)

    def test_history_baseline_excludes_future_captures_and_other_users(self):
        with patch('src.pcap_analysis.run_zeek', side_effect=self.fake_zeek), patch('src.analyses.inspect_runtime',
                   return_value=dict(fingerprints=dict(ja4='unsupported', ja4s='unsupported', ja4h='unsupported'))):
            self.upload()
        with closing(connect()) as db:
            owner = db.execute('SELECT id FROM users WHERE email=?', ('owner@example.org',)).fetchone()[0]
            other = db.execute('SELECT id FROM users WHERE email=?', ('other@example.org',)).fetchone()[0]
            self.assertIsNone(baseline_for(db, owner, 50))
            self.assertIsNone(baseline_for(db, other, 500))
            self.assertIn(('10.0.0.1', '10.0.0.2'), baseline_for(db, owner, 500)['pairs'])

    def test_restart_marks_interrupted_jobs_failed(self):
        with closing(connect()) as db:
            owner = db.execute('SELECT id FROM users WHERE email=?', ('owner@example.org',)).fetchone()[0]
            db.execute("INSERT INTO analyses(id,user_id,filename,status) VALUES('interrupted',?,'x.pcap','pending')", (owner,))
            db.commit()
            migrate(db)
            db.commit()
        response = self.client.get('/api/analyses/interrupted', headers=self.headers).json()
        self.assertEqual(response['status'], 'failed')
        self.assertIn('restart', response['error'])

    @unittest.skipUnless(os.getenv('RUN_JA4_E2E') == '1', 'Set RUN_JA4_E2E=1 with the JA4 image and reference capture installed')
    def test_real_ja4_ja4s_ja4h_reference_capture(self):
        from src.analyses import SAMPLE_DIR
        sample = SAMPLE_DIR / 'foxio-latest.pcapng'
        response = self.upload(sample.read_bytes(), sample.name)
        self.assertEqual(response.status_code, 201, response.text)
        analysis = response.json()
        for kind in ('ja4', 'ja4s', 'ja4h'):
            self.assertTrue(analysis['capabilities'][kind]['supported'], kind)
            self.assertEqual(analysis['capabilities'][kind]['status'], 'extracted')
        aid = analysis['id']
        fingerprints = self.client.get(f'/api/analyses/{aid}/fingerprints', headers=self.headers).json()['items']
        self.assertEqual({item['type'] for item in fingerprints}, {'ja4', 'ja4s', 'ja4h'})
        self.assertTrue(all(item['value'] and item['sources'] and item['connection_ids'] for item in fingerprints))
        graph = self.client.get(f'/api/analyses/{aid}/graph', headers=self.headers).json()
        self.assertTrue({'ja4', 'ja4s', 'ja4h'}.issubset({item['type'] for item in graph['nodes']}))
        self.assertEqual(self.client.get(f'/api/analyses/{aid}/fingerprints', headers=self.other).status_code, 404)
        print('REAL_JA4_COUNTS', {kind: sum(f['type'] == kind for f in fingerprints) for kind in ('ja4', 'ja4s', 'ja4h')})

    @unittest.skipUnless(os.getenv('RUN_ZEEK_E2E') == '1', 'Set RUN_ZEEK_E2E=1 with Docker/Zeek available')
    def test_real_installed_zeek_capture(self):
        capture = Path(__file__).resolve().parents[1] / 'examples' / 'zeek-conn-size.pcap'
        if not capture.is_file():
            from src.analyses import SAMPLE_DIR
            capture = SAMPLE_DIR / 'mixed.pcap'
        content = capture.read_bytes()
        self.assertIn(content[:4], PCAP_MAGIC)
        response = self.upload(content, capture.name)
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertGreater(result['summary']['connection_count'], 0)
        print('REAL_ZEEK_RESULT', json.dumps(result['summary'], sort_keys=True))
        persisted = self.client.get('/api/analyses/' + result['id'] + '/graph', headers=self.headers).json()
        self.assertGreater(len(persisted['nodes']), 0)
