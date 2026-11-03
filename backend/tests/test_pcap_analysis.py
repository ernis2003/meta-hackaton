import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from src.pcap_analysis import analyze_pcap, read_logs, run_zeek


class PcapAnalysisTests(unittest.TestCase):
    def test_upload_and_cleanup(self):
        directories = []

        def fake_zeek(directory):
            directories.append(directory)
            self.assertEqual((directory / 'capture.pcap').read_bytes()[:4], b'\xd4\xc3\xb2\xa1')
            (directory / 'conn.log').write_text(json.dumps({
                'proto': 'udp', 'service': 'dns', 'id.orig_h': '10.0.0.1',
                'id.resp_h': '10.0.0.2', 'orig_pkts': 2, 'resp_pkts': 1,
                'orig_ip_bytes': 80, 'resp_ip_bytes': 40,
            }) + '\n')

        with patch('src.pcap_analysis.run_zeek', side_effect=fake_zeek):
            result = analyze_pcap(UploadFile(filename='capture.pcap',
                                            file=io.BytesIO(b'\xd4\xc3\xb2\xa1' + b'\0' * 20)))
        self.assertEqual(result['summary']['packets'], 3)
        self.assertEqual(result['summary']['ip_bytes'], 120)
        self.assertEqual(result['summary']['services'], {'dns': 1})
        self.assertFalse(directories[0].exists())

    def test_invalid_capture_never_runs_zeek(self):
        with patch('src.pcap_analysis.run_zeek') as runner:
            with self.assertRaises(HTTPException) as error:
                analyze_pcap(UploadFile(filename='bad.pcap', file=io.BytesIO(b'no capture')))
        self.assertEqual(error.exception.status_code, 422)
        runner.assert_not_called()

    def test_truncation_preserves_total_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'conn.log').write_text('{"proto":"tcp"}\n' * 1002)
            result = read_logs(directory)
        self.assertEqual(result['summary']['connections'], 1002)
        self.assertEqual(len(result['logs']['conn']), 1000)
        self.assertEqual(result['truncated_logs'], ['conn'])

    def test_runtime_missing_and_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            for exception, status in [(FileNotFoundError(), 503),
                                      (subprocess.TimeoutExpired('zeek', 120), 504)]:
                with patch.dict('os.environ', {'ZEEK_MODE': 'native'}):
                    with patch('src.pcap_analysis.subprocess.run', side_effect=exception):
                        with self.assertRaises(HTTPException) as error:
                            run_zeek(Path(temporary))
                self.assertEqual(error.exception.status_code, status)
