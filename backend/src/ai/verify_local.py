"""Explicit real-data application inference check; saves an explanation for one existing anomaly."""
import json
import argparse
from pathlib import Path
from contextlib import closing

from fastapi.testclient import TestClient
from src.ai.common import ROOT, save_json
from src.database.connection import connect, init_db
from src.auth.authManager import create_access_token


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--regenerate', action='store_true')
    parser.add_argument('--require-fine-tuned', action='store_true')
    parser.add_argument('--output', default=str(ROOT / 'results' / 'local_inference_smoke.json'))
    args = parser.parse_args()
    if Path(args.output).exists():
        raise RuntimeError('Preserving existing verification output; choose another --output')
    from main import app
    init_db()
    with closing(connect()) as db:
        row = db.execute("SELECT e.analysis_id,e.id,a.user_id FROM analysis_entities e JOIN analyses a ON a.id=e.analysis_id "
                         "JOIN users u ON u.id=a.user_id WHERE e.kind='anomalies' AND u.is_active=1 ORDER BY a.uploaded_at DESC,e.id LIMIT 1").fetchone()
    if not row:
        raise RuntimeError('No actual stored anomaly is available; upload a capture first. No synthetic finding will be created.')
    headers = {'Authorization': 'Bearer ' + create_access_token(row['user_id'])}
    path = f"/api/analyses/{row['analysis_id']}/anomalies/{row['id']}"
    client = TestClient(app)
    response = client.post(path + '/explain' + ('?regenerate=true' if args.regenerate else ''), headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f'Local inference failed: {response.status_code} {response.text}')
    report = response.json()
    if args.require_fine_tuned and not report['fine_tuned']:
        raise RuntimeError('Verification requires the trained adapter, but the API returned a baseline report')
    cached = client.get(path + '/explanation', headers=headers)
    assert cached.status_code == 200 and cached.json()['explanation'] == report
    save_json(args.output, dict(
        analysis_id=row['analysis_id'], anomaly_id=row['id'], cache_verified=True, **report))
    print(json.dumps(dict(model=report['model_identifier'], fine_tuned=report['fine_tuned'],
                         duration_seconds=report['duration_seconds'], summary=report['report']['summary']), indent=2))


if __name__ == '__main__':
    main()
