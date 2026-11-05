"""Evidence-derived relationships. IP subjects describe addresses, not physical devices."""
from collections import defaultdict
from hashlib import sha256
from ipaddress import ip_address
from statistics import mean, pstdev
from bisect import bisect_left, bisect_right


def stable(*parts):
    return sha256('\0'.join(map(str, parts)).encode()).hexdigest()[:24]


def build_results(logs, baseline=None):
    subjects, connections, fingerprints, domains, edges = {}, [], {}, set(), {}
    anomalies = []
    by_uid = defaultdict(list)
    for kind, records in logs.items():
        if kind != 'conn':
            for record in records:
                if record.get('uid'):
                    by_uid[record['uid']].append((kind, record))

    def subject(ip):
        if ip not in subjects:
            subjects[ip] = dict(id='ip:' + ip, ip_address=ip, hostnames=[], ja4_fingerprints=[],
                                first_seen=None, last_seen=None, total_connections=0,
                                bytes_sent=0, bytes_received=0, unique_destinations=0,
                                anomaly_count=0, risk_score=0, domains=[], partners=[],
                                ports=[], protocols=[], connection_ids=[])
        return subjects[ip]

    def edge(source, target, kind, uid, **metadata):
        key = stable(source, target, kind)
        item = edges.setdefault(key, dict(id=key, source=source, target=target, type=kind,
                                         metadata=dict(connection_ids=[], connection_count=0,
                                                       total_bytes=0, protocols=[], ports=[])))
        m = item['metadata']
        if uid not in m['connection_ids']:
            m['connection_ids'].append(uid)
            m['connection_count'] += 1
            m['total_bytes'] += metadata.get('total_bytes', 0)
        for field in ('protocols', 'ports'):
            for value in metadata.get(field, []):
                if value not in m[field]:
                    m[field].append(value)

    def domain_link(host, name, uid):
        if not isinstance(name, str) or not name.strip():
            return
        name = name.lower().rstrip('.')
        domains.add(name)
        subject(host)['domains'].append(name)
        edge('ip:' + host, 'domain:' + name, 'connects_to_domain', uid)

    for index, record in enumerate(logs.get('conn', [])):
        src, dst = record.get('id.orig_h'), record.get('id.resp_h')
        if not src or not dst:
            continue
        uid = record.get('uid') or 'record-' + str(index)
        # Preserve every session even if a malformed log repeats a UID.
        cid = stable(uid, index)
        ts = record.get('ts')
        end = ts + max(record.get('duration', 0) or 0, 0) if ts is not None else None
        sent = record.get('orig_ip_bytes', record.get('orig_bytes', 0)) or 0
        received = record.get('resp_ip_bytes', record.get('resp_bytes', 0)) or 0
        ports = [record[k] for k in ('id.orig_p', 'id.resp_p') if k in record]
        proto = record.get('proto', 'unknown')
        conn = dict(id=cid, uid=uid, source=src, destination=dst, timestamp=ts,
                    last_seen=end, bytes_sent=sent, bytes_received=received, protocols=[proto],
                    source_port=record.get('id.orig_p'), destination_port=record.get('id.resp_p'),
                    service=record.get('service'), state=record.get('conn_state'),
                    domains=[], fingerprints=[], evidence=by_uid.get(uid, []))
        connections.append(conn)
        counted = set()
        for ip, outgoing, incoming, partner in ((src, sent, received, dst), (dst, received, sent, src)):
            s = subject(ip)
            if ip not in counted:
                s['total_connections'] += 1
                s['connection_ids'].append(cid)
                counted.add(ip)
            s['bytes_sent'] += outgoing
            s['bytes_received'] += incoming
            s['partners'].append(partner)
            s['ports'].extend(ports)
            s['protocols'].append(proto)
            if ts is not None:
                s['first_seen'] = min(s['first_seen'], ts) if s['first_seen'] is not None else ts
                s['last_seen'] = max(s['last_seen'], end) if s['last_seen'] is not None else end
        edge('ip:' + src, 'ip:' + dst, 'communicates_with', cid,
             total_bytes=sent + received, ports=ports, protocols=[proto])
        for kind, event in by_uid.get(uid, []):
            if kind in ('ssl', 'http'):
                name = event.get('server_name') if kind == 'ssl' else event.get('host')
                if name:
                    domain_link(src, name, cid)
                    conn['domains'].append(name)
            for field, value in event.items():
                # Only explicit JA4 fields emitted by a Zeek package are accepted.
                normalized = field.lower().replace('.', '_')
                fp_type = next((t for t in ('ja4s', 'ja4h', 'ja4')
                                if normalized == t or normalized.endswith('_' + t)), None)
                if fp_type and isinstance(value, str) and value and value != '-':
                    host = dst if fp_type == 'ja4s' else src
                    key = fp_type + ':' + value
                    fp = fingerprints.setdefault(key, dict(id=key, type=fp_type, value=value,
                                                          hosts=[], connection_ids=[], sources=[],
                                                          extraction_status='extracted'))
                    fp['hosts'].append(host)
                    fp['connection_ids'].append(cid)
                    fp['sources'].append(kind + '.log:' + field)
                    subject(host)['ja4_fingerprints'].append(key)
                    conn['fingerprints'].append(key)
                    edge('ip:' + host, key, 'uses_' + fp_type, cid)

    # DNS answers establish address/name evidence; temporal client/address matching
    # connects later sessions without incorrectly equating DNS and TLS UIDs.
    dns_sessions = defaultdict(list)
    destinations = defaultdict(set)
    for conn in connections:
        destinations[conn['source']].add(conn['destination'])
        if conn['timestamp'] is not None:
            dns_sessions[(conn['source'], conn['destination'])].append(conn)
    for records in dns_sessions.values():
        records.sort(key=lambda c: c['timestamp'])
    dns_times = {pair: [c['timestamp'] for c in records] for pair, records in dns_sessions.items()}
    for dns in logs.get('dns', []):
        query, client, ts = dns.get('query'), dns.get('id.orig_h'), dns.get('ts')
        if not query or ts is None:
            continue
        ttls = dns.get('TTLs') or []
        for i, answer in enumerate(dns.get('answers') or []):
            try:
                ip_address(answer)
            except ValueError:
                continue
            if answer in subjects:
                subjects[answer]['hostnames'].append(query)
            ttl = ttls[i] if i < len(ttls) else 0
            pair = (client, answer)
            times = dns_times.get(pair, [])
            for conn in dns_sessions.get(pair, [])[bisect_left(times, ts):bisect_right(times, ts + max(ttl, 0))]:
                domain_link(client, query, conn['id'])
                conn['domains'].append(query)

    groups = defaultdict(list)
    for conn in connections:
        groups[(conn['source'], conn['destination'])].append(conn)

    def anomaly(kind, severity, score, records, evidence):
        ips = sorted({r[k] for r in records for k in ('source', 'destination')})
        item = dict(id=stable(kind, *(r['id'] for r in records)), type=kind, severity=severity,
                    score=score, subject_ids=['ip:' + ip for ip in ips],
                    connection_ids=[r['id'] for r in records], evidence=evidence,
                    timestamp=next((r['timestamp'] for r in records if r['timestamp'] is not None), None))
        anomalies.append(item)
        for ip in ips:
            subjects[ip]['anomaly_count'] += 1
            subjects[ip]['risk_score'] = min(100, subjects[ip]['risk_score'] + score)

    for pair, records in groups.items():
        times = sorted(r['timestamp'] for r in records if r['timestamp'] is not None)
        if len(times) >= 100:
            for i in range(len(times) - 99):
                if times[i + 99] - times[i] <= 60:
                    window = [r for r in records if r['timestamp'] is not None and times[i] <= r['timestamp'] <= times[i + 99]]
                    anomaly('frequent_connections', 'medium', 25, window,
                            dict(count=len(window), window_seconds=times[i + 99] - times[i],
                                 rule='>=100 connections in a rolling 60-second window; one indicator per directed pair'))
                    break
        if len(times) >= 6:
            intervals = [b - a for a, b in zip(times, times[1:])]
            avg = mean(intervals)
            if avg >= 1 and pstdev(intervals) / avg <= .1:
                anomaly('periodic_communication', 'low', 15, records,
                        dict(mean_interval_seconds=avg, coefficient_of_variation=pstdev(intervals) / avg,
                             rule='>=6 sessions, interval >=1s, coefficient of variation <=0.1'))
        volume = sum(r['bytes_sent'] + r['bytes_received'] for r in records)
        if volume >= 100 * 1024 * 1024:
            anomaly('high_traffic_volume', 'medium', 25, records,
                    dict(bytes=volume, rule='>=100 MiB per directed pair'))
        if baseline and pair[0] in baseline['hosts'] and pair not in baseline['pairs']:
            anomaly('new_destination', 'low', 10, records,
                    dict(rule='previously observed source has a new destination', baseline_analyses=baseline['count']))
    if baseline:
        for fp in fingerprints.values():
            if fp['id'] not in baseline['fingerprints']:
                records = [c for c in connections if c['id'] in fp['connection_ids']
                           and c['source'] in baseline['hosts']]
                if records:
                    anomaly('new_fingerprint', 'low', 10, records,
                            dict(fingerprint=fp['id'], baseline_analyses=baseline['count'],
                                 rule='new fingerprint for previously observed source in user history'))
    for s in subjects.values():
        for field in ('hostnames', 'ja4_fingerprints', 'domains', 'partners', 'ports', 'protocols'):
            s[field] = sorted(set(s[field]))
        s['unique_destinations'] = len(destinations[s['ip_address']])
        observed_seconds = ((s['last_seen'] - s['first_seen'])
                            if s['last_seen'] is not None and s['first_seen'] is not None else 0)
        s['connections_per_minute'] = s['total_connections'] * 60 / observed_seconds if observed_seconds > 0 else None
    for fp in fingerprints.values():
        for field in ('hosts', 'connection_ids', 'sources'):
            fp[field] = sorted(set(fp[field]))
    capabilities = {kind: dict(status='extracted' if any(f['type'] == kind for f in fingerprints.values())
                              else 'unavailable', reason='Only explicit Zeek JA4 fields are accepted; '
                              'absence may mean unsupported package or no applicable traffic.')
                    for kind in ('ja4', 'ja4s', 'ja4h')}
    return dict(subjects=list(subjects.values()), connections=connections,
                fingerprints=list(fingerprints.values()), anomalies=anomalies,
                relationships=list(edges.values()), capabilities=capabilities,
                summary=dict(connection_count=len(connections), subject_count=len(subjects),
                             fingerprint_count=len(fingerprints), domain_count=len(domains),
                             anomaly_count=len(anomalies),
                             first_seen=min((c['timestamp'] for c in connections if c['timestamp'] is not None), default=None),
                             last_seen=max((c['last_seen'] for c in connections if c['last_seen'] is not None), default=None)))


def graph(subjects, fingerprints, relationships, anomalies):
    nodes = [dict(id=s['id'], type='host', label=s['ip_address'], metadata=s,
                  risk_score=s['risk_score'], anomaly_count=s['anomaly_count']) for s in subjects]
    nodes.extend(dict(id=f['id'], type=f['type'], label=f['value'], metadata=f,
                      risk_score=0, anomaly_count=0) for f in fingerprints)
    domains = sorted({e['target'] for e in relationships if e['type'] == 'connects_to_domain'})
    nodes.extend(dict(id=d, type='domain', label=d[7:], metadata={}, risk_score=0,
                      anomaly_count=0) for d in domains)
    anomaly_index = defaultdict(set)
    for anomaly in anomalies:
        for cid in anomaly['connection_ids']:
            anomaly_index[cid].add(anomaly['id'])
    for edge in relationships:
        edge['metadata']['anomalies'] = sorted({aid for cid in edge['metadata']['connection_ids'] for aid in anomaly_index[cid]})
    return dict(nodes=nodes, edges=relationships)
