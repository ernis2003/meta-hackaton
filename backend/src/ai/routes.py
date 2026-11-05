import json
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from src.analyses import get_analysis
from src.auth.authManager import get_current_user
from src.database import get_db
from src.ai.llm.investigator import ModelUnavailable, explain_anomaly
from src.ai.llm.schemas import Generation, MuseGeneration
from src.ai.common import digest
from src.ai.llm.muse import review

router = APIRouter(prefix='/api/analyses', tags=['AI investigations'])


class ExplanationState(BaseModel):
    status: str
    explanation: Generation | None = None
    error: str | None = None


def anomaly_record(db, analysis_id, anomaly_id, user):
    get_analysis(db, analysis_id, user)
    row = db.execute("SELECT data FROM analysis_entities WHERE analysis_id=? AND kind='anomalies' AND id=?",
                     (analysis_id, anomaly_id)).fetchone()
    if not row:
        raise HTTPException(404, 'Anomaly not found')
    return json.loads(row[0])


def evidence_for(db, analysis_id, anomaly):
    ids = set(anomaly['connection_ids'])
    # Use authoritative database evidence; sample records explicitly, never invent aggregates.
    rows = db.execute("SELECT data FROM analysis_entities WHERE analysis_id=? AND kind='connections' "
                      "AND id IN (SELECT value FROM json_each(?)) ORDER BY id",
                      (analysis_id, json.dumps(sorted(ids)))).fetchall()
    connections = [json.loads(r[0]) for r in rows]
    fields = ('id', 'uid', 'source', 'destination', 'source_port', 'destination_port', 'timestamp',
              'last_seen', 'bytes_sent', 'bytes_received', 'protocols', 'service', 'state', 'domains', 'fingerprints')
    samples = [{k: c.get(k) for k in fields} for c in connections[:8]]
    fingerprints = [json.loads(r[0]) for r in db.execute(
        "SELECT data FROM analysis_entities WHERE analysis_id=? AND kind='fingerprints' ORDER BY id", (analysis_id,))]
    linked = [dict(type=f['type'], value=f['value'], sources=f['sources'])
              for f in fingerprints if ids.intersection(f['connection_ids'])]
    addresses = sorted({c[k] for c in connections for k in ('source', 'destination')})
    return dict(anomaly={k: v for k, v in anomaly.items() if k != 'connection_ids'},
        connection_statistics=dict(stored_connections=len(connections), referenced_connections=len(ids),
            bytes_sent=sum(c['bytes_sent'] for c in connections), bytes_received=sum(c['bytes_received'] for c in connections),
            unique_endpoints=len(addresses), endpoints=addresses[:20], endpoints_truncated=len(addresses) > 20),
        connection_samples=samples, connection_samples_truncated=len(connections) > 8,
        fingerprints=linked[:10], fingerprints_truncated=len(linked) > 10,
        limitations=['Connection records are sampled when there are more than eight; totals cover all linked stored records.',
                     'Anomaly severity and score are deterministic triage indicators, not calibrated probabilities.'])


@router.get('/{analysis_id}/anomalies/{anomaly_id}/explanation', response_model=ExplanationState)
def saved_explanation(analysis_id: str, anomaly_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    anomaly_record(db, analysis_id, anomaly_id, user)
    row = db.execute('SELECT * FROM anomaly_explanations WHERE analysis_id=? AND anomaly_id=?', (analysis_id, anomaly_id)).fetchone()
    if not row:
        return dict(status='not_generated')
    status = row['status']
    if status == 'processing' and row['lease_until'] < time.time():
        return dict(status='failed', error='Previous inference was interrupted; generate again.')
    return dict(status=status, explanation=json.loads(row['result']) if row['result'] else None, error=row['error'])


@router.post('/{analysis_id}/anomalies/{anomaly_id}/explain', response_model=Generation)
def generate_explanation(analysis_id: str, anomaly_id: str, regenerate: bool = Query(False),
                         user=Depends(get_current_user), db=Depends(get_db)):
    anomaly = anomaly_record(db, analysis_id, anomaly_id, user)
    request_id = str(uuid4())
    # This short write lock is released before inference, so PCAP/history remain usable.
    try:
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute('SELECT * FROM anomaly_explanations WHERE analysis_id=? AND anomaly_id=?',
                              (analysis_id, anomaly_id)).fetchone()
        if previous and previous['status'] == 'processing' and previous['lease_until'] > time.time():
            raise HTTPException(409, 'An explanation is already being generated')
        if previous and previous['status'] == 'completed' and not regenerate:
            db.commit()
            return json.loads(previous['result'])
        db.execute('''INSERT INTO anomaly_explanations(analysis_id,anomaly_id,status,request_id,lease_until)
            VALUES(?,?,'processing',?,?) ON CONFLICT(analysis_id,anomaly_id) DO UPDATE SET
            status='processing',request_id=excluded.request_id,lease_until=excluded.lease_until,
            error=NULL,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')''',
                   (analysis_id, anomaly_id, request_id, time.time() + 240))
        db.commit()
    except Exception:
        db.rollback()
        raise
    try:
        evidence = evidence_for(db, analysis_id, anomaly)
        result = Generation.model_validate(explain_anomaly(evidence)).model_dump()
        result['evidence'] = evidence
        with db:
            changed = db.execute("UPDATE anomaly_explanations SET status='completed',result=?,error=NULL,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                                 'WHERE analysis_id=? AND anomaly_id=? AND request_id=?',
                                 (json.dumps(result), analysis_id, anomaly_id, request_id)).rowcount
            if not changed:
                raise HTTPException(409, 'Inference lease was replaced; result was not saved')
        return result
    except Exception as error:
        message = str(error) if isinstance(error, ModelUnavailable) else 'Model generation failed or returned invalid JSON; no new explanation was saved.'
        with db:
            db.execute("UPDATE anomaly_explanations SET status='failed',error=? WHERE analysis_id=? AND anomaly_id=? AND request_id=?",
                       (message, analysis_id, anomaly_id, request_id))
        raise HTTPException(503 if isinstance(error, ModelUnavailable) else 502, message) from None


def investigation_tool(db, analysis_id, anomaly, user, name):
    # Authorization is rechecked for every tool. No model-provided SQL, paths or analysis IDs.
    anomaly_record(db, analysis_id, anomaly['id'], user)
    kinds = {'related_connections': 'connections', 'host_profiles': 'subjects',
             'ja4_fingerprints': 'fingerprints', 'periodic_activity': 'anomalies'}
    if name not in kinds:
        raise ValueError('Unknown read-only investigation tool')
    ids = set(anomaly.get('connection_ids', []))
    hosts = set(anomaly.get('subject_ids', []))
    matching, total = [], 0
    for row in db.execute('SELECT data FROM analysis_entities WHERE analysis_id=? AND kind=? ORDER BY id',
                          (analysis_id, kinds[name])):
        item = json.loads(row[0])
        related = (item.get('id') in ids or 'ip:' + str(item.get('source')) in hosts
                   or 'ip:' + str(item.get('destination')) in hosts) if name == 'related_connections' else (
            item.get('id') in hosts if name == 'host_profiles' else bool(ids.intersection(item.get('connection_ids', []))))
        if name == 'periodic_activity':
            related = related and item.get('type') == 'periodic_communication'
        if related:
            total += 1
            if len(matching) < 20:
                # Array-valued host and fingerprint fields can also be large.
                matching.append({k: v[:20] if isinstance(v, list) else v for k, v in item.items()})
    return dict(items=matching, total=total, truncated=total > 20, list_field_limit=20)


@router.get('/{analysis_id}/anomalies/{anomaly_id}/review')
def saved_review(analysis_id: str, anomaly_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    anomaly_record(db, analysis_id, anomaly_id, user)
    row = db.execute('SELECT * FROM anomaly_reviews WHERE analysis_id=? AND anomaly_id=?', (analysis_id, anomaly_id)).fetchone()
    if not row:
        return dict(status='not_generated', investigation=None)
    status = row['status']
    if status == 'processing' and row['lease_until'] < time.time():
        return dict(status='failed', investigation=None, error='Previous Muse investigation was interrupted; retry.')
    result = json.loads(row['result']) if row['result'] else None
    llama = db.execute('SELECT result FROM anomaly_explanations WHERE analysis_id=? AND anomaly_id=?', (analysis_id, anomaly_id)).fetchone()
    stale = bool(result and (not llama or not llama['result'] or result['llama_report_hash'] != digest(json.loads(llama['result']))))
    return dict(status=status, investigation=result, error=row['error'], stale=stale)


@router.post('/{analysis_id}/anomalies/{anomaly_id}/investigate', response_model=MuseGeneration)
def investigate(analysis_id: str, anomaly_id: str, regenerate: bool = Query(False),
                user=Depends(get_current_user), db=Depends(get_db)):
    anomaly = anomaly_record(db, analysis_id, anomaly_id, user)
    llama_row = db.execute("SELECT result FROM anomaly_explanations WHERE analysis_id=? AND anomaly_id=? AND status='completed'",
                           (analysis_id, anomaly_id)).fetchone()
    if not llama_row:
        raise HTTPException(409, 'Analyze with Llama before requesting an independent Muse review')
    llama = json.loads(llama_row['result'])
    request_id = str(uuid4())
    try:
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute('SELECT * FROM anomaly_reviews WHERE analysis_id=? AND anomaly_id=?', (analysis_id, anomaly_id)).fetchone()
        if previous and previous['status'] == 'processing' and previous['lease_until'] > time.time():
            raise HTTPException(409, 'A Muse investigation is already running')
        if previous and previous['status'] == 'completed' and not regenerate:
            cached = json.loads(previous['result'])
            if cached['llama_report_hash'] == digest(llama):
                db.commit()
                return cached
        db.execute("""INSERT INTO anomaly_reviews(analysis_id,anomaly_id,status,request_id,lease_until)
            VALUES(?,?,'processing',?,?) ON CONFLICT(analysis_id,anomaly_id) DO UPDATE SET
            status='processing',request_id=excluded.request_id,lease_until=excluded.lease_until,error=NULL""",
                   (analysis_id, anomaly_id, request_id, time.time() + 900))
        db.commit()
    except Exception:
        db.rollback()
        raise
    try:
        evidence = evidence_for(db, analysis_id, anomaly)
        result = MuseGeneration.model_validate(review(evidence, llama,
            lambda name: investigation_tool(db, analysis_id, anomaly, user, name))).model_dump()
        with db:
            changed = db.execute("UPDATE anomaly_reviews SET status='completed',result=?,error=NULL,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE analysis_id=? AND anomaly_id=? AND request_id=?",
                (json.dumps(result), analysis_id, anomaly_id, request_id)).rowcount
            if not changed:
                raise ValueError('Investigation lease replaced')
        return result
    except Exception as error:
        message = str(error) if isinstance(error, ModelUnavailable) else 'Muse investigation failed or returned invalid JSON; no new review was saved.'
        with db:
            db.execute("UPDATE anomaly_reviews SET status='failed',error=? WHERE analysis_id=? AND anomaly_id=? AND request_id=?",
                (message, analysis_id, anomaly_id, request_id))
        raise HTTPException(503 if isinstance(error, ModelUnavailable) else 502, message) from None
