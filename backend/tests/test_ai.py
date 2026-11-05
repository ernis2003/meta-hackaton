from contextlib import closing
import json
import time
import unittest
from unittest.mock import patch

import test_analyses as helpers
from src.ai.common import ROOT, load_json
from src.ai.datasets.prepare import example
from src.ai.llm.investigator import ModelUnavailable
from src.ai.llm.schemas import parse_response
from src.ai.llm.schemas import MuseReport
from src.ai.llm.muse import review
from src.ai.common import digest
from src.database.connection import connect


def generation():
    return dict(report=dict(summary='Test response from a mocked runtime, never a production fallback.',
        observations=['Six sessions'], supporting_evidence=['Mean interval: 10 seconds'],
        possible_threats=[], benign_explanations=['Scheduled activity'], recommended_actions=['Check endpoint logs'],
        confidence='low', limitations=['Process context unavailable']),
        model_identifier='meta-llama/Llama-3.2-3B-Instruct', model_version='test-only',
        adapter_identifier=None, fine_tuned=False, generated_at='2026-11-04T00:00:00Z', duration_seconds=.1)


class AISchemaTests(unittest.TestCase):
    def test_strict_schema_rejects_invalid_confidence_missing_and_extra_fields(self):
        report = generation()['report']
        self.assertEqual(parse_response(json.dumps(report)).confidence, 'low')
        for invalid in ({**report, 'confidence': 'certain'}, {'summary': 'incomplete'}, {**report, 'extra': 'invented'}):
            with self.assertRaises(ValueError):
                parse_response(json.dumps(invalid))

    def test_fixed_controls_have_twenty_distinct_cases_and_limitations(self):
        cases = load_json(ROOT / 'evaluation' / 'control_questions.json')
        self.assertGreaterEqual(len(cases), 20)
        self.assertEqual(len({c['id'] for c in cases}), len(cases))
        self.assertTrue(all(c['expected_limitations'] and c['network_evidence']['scenario_origin'] for c in cases))

    def test_local_dataset_requires_observed_features_and_label(self):
        self.assertIsNone(example({'Label': 'Botnet'}))
        self.assertIsNone(example({'tot_pkts': 10, 'tot_bytes': 100, 'src_bytes': 50}))

    def test_cic_conversion_does_not_invent_ja4_or_attack_mechanisms(self):
        messages = example({' Label': 'BENIGN', ' Flow Duration': '100', 'Total Fwd Packets': '10',
                               'Total Backward Packets': '2', 'Flow Bytes/s': 'Infinity'})
        report = parse_response(messages[-1]['content'])
        self.assertEqual(report.possible_threats, [])
        self.assertIn('BENIGN', report.summary)
        self.assertTrue(any('No JA4' in item for item in report.limitations))


class AIAPITests(unittest.TestCase):
    setUp = helpers.AnalysisAPITests.setUp
    tearDown = helpers.AnalysisAPITests.tearDown
    register = helpers.AnalysisAPITests.register
    upload = helpers.AnalysisAPITests.upload

    def anomaly(self):
        def logs(directory):
            (directory / 'conn.log').write_text('\n'.join(json.dumps(helpers.conn(str(i), i * 10)) for i in range(6)))
        with patch('src.pcap_analysis.run_zeek', side_effect=logs), patch('src.analyses.inspect_runtime',
                   return_value=dict(fingerprints=dict(ja4='unsupported', ja4s='unsupported', ja4h='unsupported'))):
            response = self.upload()
        self.assertEqual(response.status_code, 201, response.text)
        aid = response.json()['id']
        anomaly = self.client.get(f'/api/analyses/{aid}/anomalies', headers=self.headers).json()['items'][0]
        return aid, anomaly['id']

    def test_authorization_database_evidence_and_persistent_cache(self):
        aid, anomaly_id = self.anomaly()
        path = f'/api/analyses/{aid}/anomalies/{anomaly_id}'
        self.assertEqual(self.client.post(path + '/explain').status_code, 401)
        self.assertEqual(self.client.post(path + '/explain', headers=self.other).status_code, 404)
        self.assertEqual(self.client.get(path + '/explanation', headers=self.headers).json()['status'], 'not_generated')
        captured = []
        def inference(evidence):
            captured.append(evidence)
            self.assertEqual(evidence['connection_statistics']['stored_connections'], 6)
            self.assertEqual(evidence['anomaly']['type'], 'periodic_communication')
            self.assertNotIn('fake_client_fact', evidence)
            return generation()
        with patch('src.ai.routes.explain_anomaly', side_effect=inference) as model:
            first = self.client.post(path + '/explain', headers=self.headers, json={'fake_client_fact': 'ignored'})
            self.assertEqual(first.status_code, 200, first.text)
            again = self.client.post(path + '/explain', headers=self.headers)
            self.assertEqual(again.json(), first.json())
            model.assert_called_once()
            regenerated = self.client.post(path + '/explain?regenerate=true', headers=self.headers)
            self.assertEqual(regenerated.status_code, 200)
            self.assertEqual(model.call_count, 2)
        cached = self.client.get(path + '/explanation', headers=self.headers).json()
        self.assertEqual(cached['explanation'], first.json())
        self.assertEqual(self.client.get(path + '/explanation', headers=self.other).status_code, 404)

    def test_unavailable_or_invalid_model_does_not_create_success(self):
        aid, anomaly_id = self.anomaly()
        path = f'/api/analyses/{aid}/anomalies/{anomaly_id}'
        for error, status in ((ModelUnavailable('Model unavailable'), 503), (ValueError('Invalid JSON'), 502)):
            with patch('src.ai.routes.explain_anomaly', side_effect=error):
                response = self.client.post(path + '/explain', headers=self.headers)
            self.assertEqual(response.status_code, status)
            saved = self.client.get(path + '/explanation', headers=self.headers).json()
            self.assertEqual(saved['status'], 'failed')
            self.assertIsNone(saved['explanation'])

    def test_duplicate_inference_is_rejected_with_database_lease(self):
        aid, anomaly_id = self.anomaly()
        with closing(connect()) as db, db:
            db.execute("INSERT INTO anomaly_explanations(analysis_id,anomaly_id,status,request_id,lease_until) VALUES(?,?,'processing','test',?)",
                       (aid, anomaly_id, time.time() + 120))
        with patch('src.ai.routes.explain_anomaly') as model:
            response = self.client.post(f'/api/analyses/{aid}/anomalies/{anomaly_id}/explain', headers=self.headers)
            self.assertEqual(response.status_code, 409)
            model.assert_not_called()

    def test_muse_authorization_cache_and_stale_llama_review(self):
        aid, anomaly_id = self.anomaly()
        path = f'/api/analyses/{aid}/anomalies/{anomaly_id}'
        self.assertEqual(self.client.post(path + '/investigate').status_code, 401)
        self.assertEqual(self.client.post(path + '/investigate', headers=self.other).status_code, 404)
        self.assertEqual(self.client.post(path + '/investigate', headers=self.headers).status_code, 409)
        with patch('src.ai.routes.explain_anomaly', return_value=generation()):
            self.client.post(path + '/explain', headers=self.headers)
        def reviewer(evidence, llama, retrieve):
            self.assertEqual(retrieve('related_connections')['total'], 6)
            self.assertEqual(retrieve('host_profiles')['total'], 2)
            self.assertEqual(retrieve('periodic_activity')['total'], 1)
            self.assertEqual(retrieve('ja4_fingerprints')['total'], 0)
            return dict(report=dict(verdict='inconclusive', summary='Mocked reviewer test only.',
                verified_observations=['Six stored sessions'], unsupported_claims=[], benign_explanations=['Scheduled service'],
                recommended_actions=['Review endpoint logs'], confidence='low'), model_identifier='test-muse',
                generated_at='2026-11-04T00:00:00Z', duration_seconds=.1, evidence=evidence,
                llama_report_hash=digest(llama), tool_calls=[])
        with patch('src.ai.routes.review', side_effect=reviewer) as model:
            first = self.client.post(path + '/investigate', headers=self.headers)
            self.assertEqual(first.status_code, 200, first.text)
            second = self.client.post(path + '/investigate', headers=self.headers)
            self.assertEqual(first.json(), second.json())
            model.assert_called_once()
        self.assertFalse(self.client.get(path + '/review', headers=self.headers).json()['stale'])
        changed = generation()
        changed['report']['summary'] = 'Changed test explanation'
        with patch('src.ai.routes.explain_anomaly', return_value=changed):
            self.client.post(path + '/explain?regenerate=true', headers=self.headers)
        self.assertTrue(self.client.get(path + '/review', headers=self.headers).json()['stale'])
        self.assertEqual(self.client.get(path + '/review', headers=self.other).status_code, 404)

    def test_muse_failure_preserves_local_explanation(self):
        aid, anomaly_id = self.anomaly()
        path = f'/api/analyses/{aid}/anomalies/{anomaly_id}'
        with patch('src.ai.routes.explain_anomaly', return_value=generation()):
            self.client.post(path + '/explain', headers=self.headers)
        with patch('src.ai.routes.review', side_effect=ModelUnavailable('Muse credentials unavailable')):
            self.assertEqual(self.client.post(path + '/investigate', headers=self.headers).status_code, 503)
        self.assertEqual(self.client.get(path + '/explanation', headers=self.headers).json()['status'], 'completed')
        self.assertEqual(self.client.get(path + '/review', headers=self.headers).json()['status'], 'failed')


class MuseClientTests(unittest.TestCase):
    def test_real_client_tool_loop_validates_json_and_limits_calls(self):
        import os
        from unittest.mock import MagicMock
        report = dict(verdict='inconclusive', summary='Mock HTTP response only.', verified_observations=[],
            unsupported_claims=[], benign_explanations=[], recommended_actions=[], confidence='low')
        def response(message, finish='stop'):
            result = MagicMock()
            result.json.return_value = dict(model='test-muse', choices=[dict(message=message, finish_reason=finish)])
            return result
        call = dict(id='tool-1', type='function', function=dict(name='host_profiles', arguments='{}'))
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.side_effect = [response(dict(role='assistant', content=None, tool_calls=[call]), 'tool_calls'),
                                     response(dict(role='assistant', content=json.dumps(report)))]
        with patch.dict(os.environ, {'MODEL_API_KEY': 'test-only', 'META_MUSE_MAX_TOOL_CALLS': '1'}), patch('src.ai.llm.muse.httpx.Client', return_value=client):
            retrieve = MagicMock(return_value=dict(items=[], total=0))
            result = review({}, {}, retrieve)
            self.assertEqual(result['model_identifier'], 'test-muse')
            retrieve.assert_called_once_with('host_profiles')
            self.assertNotIn('tools', client.post.call_args.kwargs['json'])
            client.post.side_effect = [response(dict(role='assistant', content=None, tool_calls=[call, call]), 'tool_calls')]
            with self.assertRaises(ValueError):
                review({}, {}, retrieve)
        with self.assertRaises(ValueError):
            MuseReport.model_validate({**report, 'confidence': 'certain'})
