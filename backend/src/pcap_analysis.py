"""Offline PCAP analysis using Zeek JSON logs."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import shlex
import re
import logging
from collections import Counter

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from src.auth.authManager import get_current_user

router = APIRouter(prefix='/api/pcap', tags=['PCAP analysis'])
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_LOG_BYTES = 200 * 1024 * 1024
MAX_RECORDS_PER_LOG = 1000
PCAP_MAGIC = {b'\xd4\xc3\xb2\xa1', b'\xa1\xb2\xc3\xd4',
              b'\x4d\x3c\xb2\xa1', b'\xa1\xb2\x3c\x4d', b'\x0a\x0d\x0d\x0a'}


def run_zeek(directory: Path):
    mode = os.getenv('ZEEK_MODE', 'docker' if os.name == 'nt' else 'native')
    args = ['-C', '-r', 'capture.pcap', 'LogAscii::use_json=T',
            *shlex.split(os.getenv('ZEEK_SCRIPTS', ''))]
    container_name = 'pcap-zeek-' + directory.name
    if mode == 'docker':
        command = ['docker', 'run', '--rm', '--name', container_name,
                   '--network', 'none', '--memory', '1g', '--cpus', '2',
                   '--mount', f'type=bind,source={directory.resolve()},target=/work',
                   '--workdir', '/work', '--entrypoint', 'zeek',
                   os.getenv('ZEEK_DOCKER_IMAGE', 'zeek/zeek:latest'), *args]
    elif mode == 'native':
        command = [os.getenv('ZEEK_BIN', 'zeek'), *args]
    else:
        raise HTTPException(503, 'ZEEK_MODE must be native or docker')
    try:
        with (directory / 'stderr.txt').open('wb') as errors:
            result = subprocess.run(command, cwd=directory, stdout=subprocess.DEVNULL,
                                    stderr=errors, timeout=120, check=False)
    except FileNotFoundError:
        raise HTTPException(503, 'Zeek runtime unavailable. Configure ZEEK_MODE and install Zeek or Docker.') from None
    except subprocess.TimeoutExpired:
        if mode == 'docker':
            try:
                subprocess.run(['docker', 'rm', '-f', container_name],
                               capture_output=True, timeout=15, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
        raise HTTPException(504, 'Zeek analysis exceeded 120 seconds') from None
    if result.returncode:
        details = (directory / 'stderr.txt').read_text(encoding='utf-8', errors='replace')
        logging.getLogger(__name__).error('Zeek failed (mode=%s, exit=%s): %s',
                                         mode, result.returncode, details[-8000:])
        if mode == 'docker':
            if any(message in details.lower() for message in (
                    'cannot connect', 'error during connect', 'is the docker daemon running',
                    'docker desktop is unable to start')):
                raise HTTPException(503, 'Docker is not running. Start Docker Desktop and wait for its engine to be ready, then retry.')
            if result.returncode in (125, 126, 127):
                raise HTTPException(503, 'Zeek container could not start. Check the configured Docker image and Zeek executable; see backend logs.')
        raise HTTPException(422, 'Zeek could not process the capture. Check the capture format; see backend logs for details.')


def read_logs(directory: Path, limit=MAX_RECORDS_PER_LOG):
    logs, counts = {}, {}
    protocols, services = Counter(), Counter()
    hosts = set()
    connections = packets = byte_count = 0
    total_log_bytes = 0
    for path in sorted(directory.glob('*.log')):
        records = []
        count = 0
        with path.open('rb') as stream:
            while True:
                line = stream.readline(MAX_LOG_BYTES + 1)
                if not line:
                    break
                total_log_bytes += len(line)
                if total_log_bytes > MAX_LOG_BYTES:
                    raise HTTPException(422, 'Zeek logs exceed the analysis size limit')
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError('Expected object')
                except (ValueError, UnicodeDecodeError):
                    raise HTTPException(502, 'Zeek produced an invalid JSON log') from None
                count += 1
                if limit is None or len(records) < limit:
                    records.append(record)
                if path.stem == 'conn':
                    connections += 1
                    protocols[record.get('proto') or 'unknown'] += 1
                    services[record.get('service') or 'unknown'] += 1
                    hosts.update(record[key] for key in ('id.orig_h', 'id.resp_h') if isinstance(record.get(key), str))
                    packets += sum(record.get(key, 0) or 0 for key in ('orig_pkts', 'resp_pkts'))
                    byte_count += sum(record.get(key, 0) or 0 for key in ('orig_ip_bytes', 'resp_ip_bytes'))
        logs[path.stem] = records
        counts[path.stem] = count
    return {'summary': {'connections': connections, 'hosts': sorted(hosts),
                        'packets': packets, 'ip_bytes': byte_count,
                        'protocols': dict(protocols), 'services': dict(services)},
            'logs': logs, 'log_counts': counts,
            'truncated_logs': [key for key, count in counts.items() if limit is not None and count > limit]}


def analyze_pcap(file: UploadFile, limit=MAX_RECORDS_PER_LOG):
    """Return Zeek logs (up to 1,000 rows per log) and full connection totals."""
    try:
        if Path(file.filename or '').suffix.lower() not in {'.pcap', '.pcapng'}:
            raise HTTPException(415, 'Upload a .pcap or .pcapng file')
        with tempfile.TemporaryDirectory(prefix='pcap-') as temporary:
            directory = Path(temporary)
            size = 0
            with (directory / 'capture.pcap').open('wb') as destination:
                while chunk := file.file.read(1024 * 1024):
                    if size == 0 and (len(chunk) < 24 or chunk[:4] not in PCAP_MAGIC):
                        raise HTTPException(422, 'Invalid PCAP or PCAPNG header')
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(413, 'Capture exceeds the 100 MiB limit')
                    destination.write(chunk)
            if not size:
                raise HTTPException(422, 'Capture is empty')
            run_zeek(directory)
            return {'filename': file.filename, 'size_bytes': size, **read_logs(directory, limit)}
    finally:
        file.file.close()


def inspect_runtime():
    """Inspect the same runtime and scripts used for captures, without network access."""
    mode = os.getenv('ZEEK_MODE', 'docker' if os.name == 'nt' else 'native')
    prefix = ([os.getenv('ZEEK_BIN', 'zeek')] if mode == 'native' else
              ['docker', 'run', '--rm', '--network', 'none', '--memory', '256m', '--cpus', '1',
               '--entrypoint', 'zeek', os.getenv('ZEEK_DOCKER_IMAGE', 'zeek/zeek:latest')])
    result = {'mode': mode, 'version': None, 'fingerprints': {}}
    try:
        version = subprocess.run([*prefix, '--version'], capture_output=True, text=True, timeout=20)
        result['version'] = version.stdout.strip() if version.returncode == 0 else None
        schema = subprocess.run([*prefix, '-e', 'print record_fields(SSL::Info); print record_fields(HTTP::Info);',
                                 *shlex.split(os.getenv('ZEEK_SCRIPTS', ''))],
                                capture_output=True, text=True, timeout=20)
        for kind in ('ja4', 'ja4s', 'ja4h'):
            supported = schema.returncode == 0 and bool(re.search(r'\[(?:\w+_)?' + kind + r'\]', schema.stdout, re.I))
            result['fingerprints'][kind] = 'supported' if supported else ('unsupported' if schema.returncode == 0 else 'unavailable')
    except (OSError, subprocess.TimeoutExpired):
        result['fingerprints'] = dict.fromkeys(('ja4', 'ja4s', 'ja4h'), 'unavailable')
    return result


@router.post('/analyze')
def persistent_analyze(file: UploadFile = File(...), user=Depends(get_current_user)):
    # Keep the existing public route and share exactly the same persistence pipeline.
    from contextlib import closing
    from src.database.connection import connect
    from src.analyses import create_analysis
    with closing(connect()) as db:
        return create_analysis(file=file, user=user, db=db)
