"""User-scoped durable analysis API; result entities stored once, graphs reconstructed."""
import json
import time
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from src.auth.authManager import get_current_user
from src.database import get_db
from src.forensics import build_results, graph
from src.pcap_analysis import analyze_pcap, inspect_runtime

router = APIRouter(prefix='/api/analyses', tags=['Analyses'])
KINDS = ('subjects', 'connections', 'fingerprints', 'relationships', 'anomalies')
EXAMPLE = Path(__file__).resolve().parents[1] / 'examples' / 'zeek-conn-size.pcap'
SAMPLE_DIR = Path(__file__).resolve().parent / 'data' / 'pcap_samples'


def installed_examples():
    # Fixed allowlist: never interpret a request name as a filesystem path.
    paths = [EXAMPLE, *(SAMPLE_DIR / name for name in (
        'normal.pcap', 'suspicious.pcap', 'mixed.pcap', 'foxio-latest.pcapng'))]
    return {path.name: path for path in paths if path.is_file()}


class Analysis(BaseModel):
    id: str
    filename: str
    uploaded_at: str
    status: str
    duration_seconds: float | None = None
    error: str | None = None
    summary: dict = Field(default_factory=dict)
    capabilities: dict = Field(default_factory=dict)
    status_history: list[dict] = Field(default_factory=list)


class Page(BaseModel):
    items: list[dict]
    total: int
    limit: int
    offset: int


class Graph(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    total_nodes: int
    total_edges: int
    truncated: bool


@router.get('/examples', response_model=Page)
def examples(user=Depends(get_current_user)):
    items = [dict(id=name, filename=name, size_bytes=path.stat().st_size,
                  description='Existing capture sample. Filename is not a verified safety or malware verdict.')
             for name, path in installed_examples().items()]
    return dict(items=items, total=len(items), limit=25, offset=0)


@router.post('/examples/{name}', response_model=Analysis, status_code=201)
def analyze_example(name: str, user=Depends(get_current_user), db=Depends(get_db)):
    path = installed_examples().get(name)
    if path is None:
        raise HTTPException(404, 'Example capture not installed')
    return create_analysis(UploadFile(filename=name, file=path.open('rb')), user, db)


def get_analysis(db, analysis_id, user):
    row = db.execute('SELECT * FROM analyses WHERE id=? AND user_id=?', (analysis_id, user['id'])).fetchone()
    if not row:
        raise HTTPException(404, 'Analysis not found')
    result = dict(row)
    result.pop('user_id')
    for key in ('summary', 'capabilities'):
        result[key] = json.loads(result[key])
    result['status_history'] = [dict(r) for r in db.execute(
        'SELECT status,timestamp FROM analysis_status_events WHERE analysis_id=? ORDER BY sequence', (analysis_id,))]
    return result


def entities(db, analysis_id, kind):
    return [json.loads(r[0]) for r in db.execute(
        'SELECT data FROM analysis_entities WHERE analysis_id=? AND kind=? ORDER BY id', (analysis_id, kind))]


def baseline_for(db, user_id, before):
    if before is None:
        return None
    rows = db.execute("SELECT id FROM analyses WHERE user_id=? AND status='completed'", (user_id,)).fetchall()
    if not rows:
        return None
    result = dict(hosts=set(), pairs=set(), fingerprints=set(), count=0)
    for row in rows:
        historical_ids = set()
        for c in entities(db, row[0], 'connections'):
            if c['last_seen'] is None or c['last_seen'] >= before:
                continue
            historical_ids.add(c['id'])
            result['hosts'].add(c['source'])
            result['pairs'].add((c['source'], c['destination']))
        if historical_ids:
            result['count'] += 1
        result['fingerprints'].update(f['id'] for f in entities(db, row[0], 'fingerprints')
                                      if historical_ids.intersection(f['connection_ids']))
    return result if result['count'] else None


@router.post('', response_model=Analysis, status_code=201)
def create_analysis(file: UploadFile = File(...), user=Depends(get_current_user), db=Depends(get_db)):
    analysis_id = str(uuid4())
    start = time.monotonic()
    with db:
        db.execute('INSERT INTO analyses(id,user_id,filename,status) VALUES(?,?,?,?)',
                   (analysis_id, user['id'], file.filename or '', 'pending'))
    try:
        with db:
            db.execute("UPDATE analyses SET status='processing' WHERE id=?", (analysis_id,))
        parsed = analyze_pcap(file, limit=None)
        runtime = inspect_runtime()
        first_observed = min((r['ts'] for r in parsed['logs'].get('conn', []) if r.get('ts') is not None), default=None)
        results = build_results(parsed['logs'], baseline_for(db, user['id'], first_observed))
        for kind, capability in results['capabilities'].items():
            capability['supported'] = (runtime['fingerprints'].get(kind) == 'supported'
                                       or capability['status'] == 'extracted')
            if capability['status'] != 'extracted':
                supported = runtime['fingerprints'].get(kind, 'unavailable')
                capability['status'] = 'no_applicable_traffic' if supported == 'supported' else supported
                capability['reason'] = ('No applicable fingerprint observed in this capture.' if supported == 'supported'
                                        else 'Runtime has no active JA4 log field. Install FoxIO JA4 and load packages via ZEEK_SCRIPTS.')
            capability['runtime'] = runtime
        with db:
            for kind in KINDS:
                db.executemany('INSERT INTO analysis_entities VALUES(?,?,?,?)',
                               [(analysis_id, kind, item['id'], json.dumps(item)) for item in results[kind]])
            results['summary'].update(parsed['summary'])
            db.execute("UPDATE analyses SET status='completed',duration_seconds=?,summary=?,capabilities=? WHERE id=?",
                       (time.monotonic() - start, json.dumps(results['summary']),
                        json.dumps(results['capabilities']), analysis_id))
    except Exception as error:
        message = error.detail if isinstance(error, HTTPException) else 'Analysis failed; check server logs'
        if not isinstance(error, HTTPException):
            import logging
            logging.getLogger(__name__).exception('Analysis %s failed', analysis_id)
        with db:
            db.execute("UPDATE analyses SET status='failed',duration_seconds=?,error=? WHERE id=?",
                       (time.monotonic() - start, str(message), analysis_id))
        raise HTTPException(error.status_code if isinstance(error, HTTPException) else 500,
                            dict(analysis_id=analysis_id, status='failed', message=message)) from None
    finally:
        file.file.close()
    return get_analysis(db, analysis_id, user)


@router.get('', response_model=Page)
def list_analyses(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                  user=Depends(get_current_user), db=Depends(get_db)):
    ids = db.execute('SELECT id FROM analyses WHERE user_id=? ORDER BY uploaded_at DESC,id LIMIT ? OFFSET ?',
                     (user['id'], limit, offset)).fetchall()
    total = db.execute('SELECT COUNT(*) FROM analyses WHERE user_id=?', (user['id'],)).fetchone()[0]
    return dict(items=[get_analysis(db, r[0], user) for r in ids], total=total, limit=limit, offset=offset)


@router.get('/{analysis_id}', response_model=Analysis)
@router.get('/{analysis_id}/status', response_model=Analysis)
def detail(analysis_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    return get_analysis(db, analysis_id, user)


@router.get('/{analysis_id}/graph', response_model=Graph)
def analysis_graph(analysis_id: str, limit: int = Query(300, ge=1, le=1000),
                   search: str = '', focus: str = '', user=Depends(get_current_user), db=Depends(get_db)):
    get_analysis(db, analysis_id, user)
    result = graph(*(entities(db, analysis_id, kind) for kind in ('subjects', 'fingerprints', 'relationships', 'anomalies')))
    nodes, edges = result['nodes'], result['edges']
    if search:
        matches = {n['id'] for n in nodes if search.lower() in n['label'].lower()}
        neighbors = {e[k] for e in edges if e['source'] in matches or e['target'] in matches for k in ('source', 'target')}
        nodes = [n for n in nodes if n['id'] in matches | neighbors]
    if focus:
        related = {focus} | {e[k] for e in edges if focus in (e['source'], e['target']) for k in ('source', 'target')}
        nodes = [n for n in nodes if n['id'] in related]
    total_nodes = len(nodes)
    nodes.sort(key=lambda n: (-n['risk_score'], n['id']))
    nodes = nodes[:limit]
    ids = {n['id'] for n in nodes}
    selected = [e for e in edges if e['source'] in ids and e['target'] in ids]
    for item in [*nodes, *selected[:2000]]:
        metadata = item['metadata']
        for key in ('connection_ids', 'partners'):
            values = metadata.get(key, [])
            if len(values) > 200:
                metadata[key + '_total'] = len(values)
                metadata[key + '_truncated'] = True
                metadata[key] = values[:200]
    return dict(nodes=nodes, edges=selected[:2000], total_nodes=total_nodes,
                total_edges=len(selected), truncated=total_nodes > limit or len(selected) > 2000)


@router.get('/{analysis_id}/activity/{subject_id}')
def subject_activity(analysis_id: str, subject_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    get_analysis(db, analysis_id, user)
    subject = next((s for s in entities(db, analysis_id, 'subjects') if s['id'] == subject_id), None)
    if not subject:
        raise HTTPException(404, 'Subject not found')
    rows = db.execute("SELECT data FROM analysis_entities WHERE analysis_id=? AND kind='connections' "
                      "AND (json_extract(data, '$.source')=? OR json_extract(data, '$.destination')=?)",
                      (analysis_id, subject['ip_address'], subject['ip_address'])).fetchall()
    connections = [json.loads(row[0]) for row in rows]
    timed = [c for c in connections if c.get('timestamp') is not None]
    start = min((c['timestamp'] for c in timed), default=None)
    end = max((c.get('last_seen') or c['timestamp'] for c in timed), default=None)
    interval = max((end - start) / 32, 1) if start is not None else 1
    buckets = [dict(timestamp=start + i * interval, sent=0, received=0, connections=0)
               for i in range(32)] if start is not None else []
    peers = {}
    for connection in connections:
        outgoing = connection['source'] == subject['ip_address']
        connection['subject_sent'] = connection['bytes_sent'] if outgoing else connection['bytes_received']
        connection['subject_received'] = connection['bytes_received'] if outgoing else connection['bytes_sent']
        connection['peer'] = connection['destination'] if outgoing else connection['source']
        peer = peers.setdefault(connection['peer'], dict(ip=connection['peer'], sent=0, received=0, connections=0))
        for key, value in (('sent', connection['subject_sent']), ('received', connection['subject_received']), ('connections', 1)):
            peer[key] += value
        if connection.get('timestamp') is not None:
            bucket = buckets[min(31, int((connection['timestamp'] - start) / interval))]
            bucket['sent'] += connection['subject_sent']
            bucket['received'] += connection['subject_received']
            bucket['connections'] += 1
    connections.sort(key=lambda c: c.get('timestamp') or 0, reverse=True)
    return dict(subject=subject, buckets=buckets, interval_seconds=interval,
                peers=sorted(peers.values(), key=lambda p: -(p['sent'] + p['received']))[:20],
                connections=connections[:50], total_connections=len(connections),
                untimed_connections=len(connections) - len(timed))


@router.get('/{analysis_id}/{kind}', response_model=Page)
def results_page(analysis_id: str, kind: str, limit: int = Query(50, ge=1, le=200),
                 offset: int = Query(0, ge=0), subject_id: str = '', connection_id: str = '',
                 anomaly_type: str = '', anomaly_ids: str | None = None,
                 user=Depends(get_current_user), db=Depends(get_db)):
    get_analysis(db, analysis_id, user)
    if kind not in KINDS:
        raise HTTPException(404, 'Unknown result collection')
    conditions = ['analysis_id=?', 'kind=?']
    params = [analysis_id, kind]
    if subject_id:
        conditions.append("EXISTS (SELECT 1 FROM json_each(data, '$.subject_ids') WHERE value=?)")
        params.append(subject_id)
    if connection_id:
        conditions.append("EXISTS (SELECT 1 FROM json_each(data, '$.connection_ids') WHERE value=?)")
        params.append(connection_id)
    if anomaly_type:
        conditions.append("json_extract(data, '$.type') IN (SELECT value FROM json_each(?))")
        params.append(json.dumps(anomaly_type.split(',')))
    if anomaly_ids is not None:
        conditions.append('id IN (SELECT value FROM json_each(?))')
        params.append(json.dumps(anomaly_ids.split(',')))
    where = ' AND '.join(conditions)
    total = db.execute('SELECT COUNT(*) FROM analysis_entities WHERE ' + where, params).fetchone()[0]
    rows = db.execute('SELECT data FROM analysis_entities WHERE ' + where + ' ORDER BY id LIMIT ? OFFSET ?',
                      (*params, limit, offset)).fetchall()
    return dict(items=[json.loads(r[0]) for r in rows], total=total, limit=limit, offset=offset)
