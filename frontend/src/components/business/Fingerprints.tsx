import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faFingerprint,
  faShieldHalved,
  faLayerGroup,
  faDiagramProject,
  faMagnifyingGlass,
  faArrowUpFromBracket,
  faCopy,
  faXmark,
  faDesktop,
  faCalendarDays,
  faArrowUpRightFromSquare,
  faChevronLeft,
  faChevronRight,
} from '@fortawesome/free-solid-svg-icons';
import { api, selectAnalysis, useAnalysis, type Analysis, type Page } from '../../utils/analyses';
import styles from './Fingerprints.module.css';

type FingerprintType = 'ja4' | 'ja4s' | 'ja4h';
type Fingerprint = {
  id: string;
  type: FingerprintType;
  value: string;
  hosts: string[];
  connection_ids: string[];
  sources: string[];
};
type Connection = {
  id: string;
  uid: string;
  source: string;
  destination: string;
  timestamp: number | null;
  service: string | null;
  protocols: string[];
  domains: string[];
  fingerprints: string[];
  evidence: [string, Record<string, unknown>][];
};
type Dataset = { fingerprints: Fingerprint[]; connections: Connection[] };
type Row = { connection: Connection; ja4: Fingerprint[]; ja4s: Fingerprint[]; ja4h: Fingerprint[] };
const kinds: FingerprintType[] = ['ja4', 'ja4s', 'ja4h'];
const pageSize = 10;

async function readAll<T>(path: string, limit: number, signal: AbortSignal): Promise<T[]> {
  const join = path.includes('?') ? '&' : '?';
  const first = await api<Page<T>>(`${path}${join}limit=${limit}&offset=0`, { signal });
  const items = [...first.items];
  for (let offset = limit; offset < first.total; offset += limit * 4) {
    const offsets = Array.from({ length: 4 }, (_, i) => offset + i * limit).filter(
      (value) => value < first.total,
    );
    const pages = await Promise.all(
      offsets.map((value) =>
        api<Page<T>>(`${path}${join}limit=${limit}&offset=${value}`, { signal }),
      ),
    );
    for (const page of pages) items.push(...page.items);
  }
  return items;
}
function protocol(connection: Connection) {
  return connection.service === 'ssl'
    ? 'TLS'
    : (connection.service || connection.protocols.join(', ') || 'Unknown').toUpperCase();
}
function observedTime(timestamp: number | null, full = false) {
  if (timestamp === null) return 'Not recorded';
  const date = new Date(timestamp * 1000);
  return full ? date.toLocaleString() : date.toLocaleTimeString();
}
function context(connection: Connection) {
  let sni = '',
    userAgent = '';
  for (const [kind, event] of connection.evidence || []) {
    if (kind === 'ssl' && typeof event.server_name === 'string') sni = event.server_name;
    if (kind === 'http' && typeof event.user_agent === 'string') userAgent = event.user_agent;
  }
  return { sni, userAgent };
}
function csvCell(value: string) {
  const safe = /^[\s]*[=+\-@\t\r]/.test(value) ? "'" + value : value;
  return '"' + safe.replaceAll('"', '""') + '"';
}
function exportCsv(rows: Row[], filename: string) {
  const columns = [
    'Observed',
    'Source IP',
    'Destination IP',
    'Protocol',
    'JA4',
    'JA4S',
    'JA4H',
    'Domains',
  ];
  const records = rows.map((row) => [
    observedTime(row.connection.timestamp, true),
    row.connection.source,
    row.connection.destination,
    protocol(row.connection),
    ...kinds.map((kind) => row[kind].map((fp) => fp.value).join('; ')),
    row.connection.domains.join('; '),
  ]);
  const content = [columns, ...records].map((values) => values.map(csvCell).join(',')).join('\r\n');
  const url = URL.createObjectURL(
    new Blob(['\uFEFF' + content], { type: 'text/csv;charset=utf-8' }),
  );
  const link = document.createElement('a');
  link.href = url;
  link.download = filename.replace(/[^a-zA-Z0-9._-]/g, '_') + '-fingerprints.csv';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function FingerprintValue({
  values,
  onCopy,
}: {
  values: Fingerprint[];
  onCopy: (value: string) => void;
}) {
  if (!values.length)
    return (
      <span className={styles.absent} aria-label="Not observed">
        &mdash;
      </span>
    );
  return (
    <div className={styles.fingerprintValues}>
      {values.map((fp) => (
        <div key={fp.id} className={styles.fingerprintValue}>
          <span className={styles.hash} title={fp.value}>
            {fp.value}
          </span>
          <button
            className={styles.copy}
            type="button"
            aria-label={`Copy ${fp.type.toUpperCase()} fingerprint`}
            title="Copy fingerprint"
            onClick={(event) => {
              event.stopPropagation();
              onCopy(fp.value);
            }}
          >
            <FontAwesomeIcon icon={faCopy} />
          </button>
        </div>
      ))}
    </div>
  );
}
export default function Fingerprints() {
  const [params, setParams] = useSearchParams();
  const storedId = useAnalysis();
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{
    attempt: number;
    analyses?: Analysis[];
    examples?: string[];
    error?: string;
  }>();
  const [processing, setProcessing] = useState(false);
  const [actionError, setActionError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      readAll<Analysis>('', 100, controller.signal),
      api<Page<{ id: string }>>('/examples', { signal: controller.signal }),
    ])
      .then(([analyses, examples]) => {
        if (!controller.signal.aborted)
          setState({ attempt, analyses, examples: examples.items.map((item) => item.id) });
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted) setState({ attempt, error: error.message });
      });
    return () => controller.abort();
  }, [attempt]);
  const current = state?.attempt === attempt ? state : undefined;
  const analyses = current?.analyses;
  const requested = params.get('analysis');
  const previousSelection = analyses?.find((a) => a.id === (requested || storedId));
  // Explicit history links retain their original results. A stale session-only
  // selection may use a newer, genuinely extracted analysis after runtime setup.
  const upgraded =
    !requested &&
    previousSelection &&
    !Number(previousSelection.summary.fingerprint_count) &&
    kinds.some((kind) => previousSelection.capabilities[kind]?.status === 'unsupported')
      ? analyses?.find(
          (a) =>
            a.status === 'completed' &&
            Number(a.summary.fingerprint_count) > 0 &&
            kinds.every((kind) => a.capabilities[kind]?.supported),
        )
      : undefined;
  const selected =
    upgraded ||
    previousSelection ||
    (!requested ? analyses?.find((a) => a.status === 'completed') || analyses?.[0] : undefined);
  async function analyzeExample(name: string) {
    if (processing) return;
    setProcessing(true);
    setActionError('');
    try {
      const result = await api<Analysis>(`/examples/${encodeURIComponent(name)}`, {
        method: 'POST',
      });
      setState((previous) => ({
        attempt,
        analyses: [result, ...(previous?.analyses || [])],
        examples: previous?.examples,
      }));
      selectAnalysis(result.id);
      setParams((previous) => {
        const next = new URLSearchParams(previous);
        next.set('analysis', result.id);
        return next;
      });
    } catch (error) {
      setActionError((error as Error).message);
    } finally {
      setProcessing(false);
    }
  }
  return (
    <div className={styles.page}>
      <div className={styles.breadcrumb}>
        <FontAwesomeIcon icon={faFingerprint} />
        JA4+ Fingerprints
      </div>
      <header className={styles.header}>
        <div>
          <h1>JA4+ Fingerprints</h1>
          <p>
            TLS (JA4), Server TLS (JA4S) and HTTP (JA4H) fingerprints extracted from analyzed
            traffic.
          </p>
        </div>
        <div className={styles.analysisControls}>
          <label className={styles.analysisSelect}>
            <span>Analysis:</span>
            <select
              aria-label="Select analysis"
              disabled={!analyses?.length}
              value={selected?.id || ''}
              onChange={(event) => {
                selectAnalysis(event.target.value);
                setParams((previous) => {
                  const next = new URLSearchParams(previous);
                  next.set('analysis', event.target.value);
                  return next;
                });
              }}
            >
              {!selected && <option value="">Select analysis</option>}
              {analyses?.map((analysis) => (
                <option key={analysis.id} value={analysis.id}>
                  {analysis.filename}
                  {analysis.status !== 'completed' ? ` (${analysis.status})` : ''}
                </option>
              ))}
            </select>
          </label>
          {selected && (
            <span className={styles.analyzed}>
              <FontAwesomeIcon icon={faCalendarDays} />
              Uploaded: {new Date(selected.uploaded_at).toLocaleString()}
            </span>
          )}
        </div>
      </header>
      <div className={styles.sampleActions}>
        {current?.examples?.includes('foxio-latest.pcapng') && (
          <button
            type="button"
            className={styles.button}
            disabled={processing}
            onClick={() => void analyzeExample('foxio-latest.pcapng')}
          >
            Analyze JA4+ reference capture
          </button>
        )}
        {selected && current?.examples?.includes(selected.filename) && (
          <button
            type="button"
            className={styles.button}
            disabled={processing}
            onClick={() => void analyzeExample(selected.filename)}
          >
            Reanalyze selected capture
          </button>
        )}
        {processing && <span role="status">Extracting fingerprints with Zeek...</span>}
      </div>
      {actionError && (
        <p role="alert" className={styles.error}>
          {actionError}
        </p>
      )}
      {!current && (
        <p className={styles.state} role="status">
          Loading saved analyses...
        </p>
      )}
      {current?.error && (
        <div role="alert" className={styles.error}>
          {current.error}
          <button type="button" className={styles.button} onClick={() => setAttempt(attempt + 1)}>
            Try again
          </button>
        </div>
      )}
      {analyses?.length === 0 && (
        <div className={styles.state}>
          <h2>No analyses yet</h2>
          <p>Upload a capture to inspect its recorded fingerprints.</p>
          <Link className={styles.button} to="/user/dashboard">
            Upload capture
          </Link>
        </div>
      )}
      {analyses && analyses.length > 0 && !selected && (
        <p className={styles.error} role="alert">
          The selected analysis is not available. Choose an analysis above.
        </p>
      )}
      {selected && selected.status !== 'completed' && (
        <p className={styles.state} role={selected.status === 'failed' ? 'alert' : 'status'}>
          {selected.error ||
            'This analysis has not completed. Fingerprints will be available after processing.'}
        </p>
      )}
      {selected?.status === 'completed' && (
        <FingerprintExplorer key={selected.id} analysis={selected} />
      )}
    </div>
  );
}

function FingerprintExplorer({ analysis }: { analysis: Analysis }) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ attempt: number; data?: Dataset; error?: string }>();
  const [search, setSearch] = useState('');
  const [type, setType] = useState('all');
  const [service, setService] = useState('all');
  const [subject, setSubject] = useState('all');
  const [page, setPage] = useState(0);
  const [ascending, setAscending] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>();
  const [notice, setNotice] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      const fingerprints = await readAll<Fingerprint>(
        `/${analysis.id}/fingerprints`,
        200,
        controller.signal,
      );
      const connections = fingerprints.length
        ? await readAll<Connection>(`/${analysis.id}/connections`, 200, controller.signal)
        : [];
      return { fingerprints, connections };
    }
    load()
      .then((data) => {
        if (!controller.signal.aborted) setState({ attempt, data });
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted) setState({ attempt, error: error.message });
      });
    return () => controller.abort();
  }, [analysis.id, attempt]);
  const current = state?.attempt === attempt ? state : undefined;
  const data = current?.data;
  const rows = useMemo(() => {
    if (!data) return [];
    const related = new Map<string, Fingerprint[]>();
    for (const fp of data.fingerprints)
      for (const id of fp.connection_ids) {
        const entries = related.get(id) || [];
        entries.push(fp);
        related.set(id, entries);
      }
    return data.connections
      .filter((connection) => related.has(connection.id))
      .map((connection) => {
        const entries = related.get(connection.id) || [];
        return {
          connection,
          ja4: entries.filter((fp) => fp.type === 'ja4'),
          ja4s: entries.filter((fp) => fp.type === 'ja4s'),
          ja4h: entries.filter((fp) => fp.type === 'ja4h'),
        };
      });
  }, [data]);
  const filtered = rows
    .filter((row) => {
      const connection = row.connection;
      const text = [
        connection.source,
        connection.destination,
        ...connection.domains,
        ...kinds.flatMap((kind) => row[kind].map((fp) => fp.value)),
      ]
        .join(' ')
        .toLowerCase();
      return (
        (!search || text.includes(search.toLowerCase())) &&
        (type === 'all' || row[type as FingerprintType].length > 0) &&
        (service === 'all' || protocol(connection) === service) &&
        (subject === 'all' || connection.source === subject)
      );
    })
    .sort((a, b) =>
      ascending
        ? (a.connection.timestamp ?? 0) - (b.connection.timestamp ?? 0)
        : (b.connection.timestamp ?? 0) - (a.connection.timestamp ?? 0),
    );
  const pages = Math.ceil(filtered.length / pageSize);
  const actualPage = Math.min(page, Math.max(0, pages - 1));
  const visible = filtered.slice(actualPage * pageSize, (actualPage + 1) * pageSize);
  const selected = filtered.find(
    (row) =>
      row.connection.id === (selectedId === undefined ? filtered[0]?.connection.id : selectedId),
  );
  const details = selected ? context(selected.connection) : undefined;
  const services = [...new Set(rows.map((row) => protocol(row.connection)))].sort();
  const subjects = [...new Set(rows.map((row) => row.connection.source))].sort();
  function changeFilter(update: () => void) {
    update();
    setPage(0);
    setSelectedId(undefined);
  }
  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNotice('Fingerprint copied to clipboard.');
    } catch {
      setNotice(
        'Clipboard access unavailable. Select the full value in Fingerprint Details to copy it.',
      );
    }
  }
  const metrics = [
    {
      title: 'Unique JA4',
      icon: faFingerprint,
      value: data?.fingerprints.filter((fp) => fp.type === 'ja4').length,
    },
    {
      title: 'Unique JA4S',
      icon: faShieldHalved,
      value: data?.fingerprints.filter((fp) => fp.type === 'ja4s').length,
    },
    {
      title: 'Unique JA4H',
      icon: faLayerGroup,
      value: data?.fingerprints.filter((fp) => fp.type === 'ja4h').length,
    },
    {
      title: 'Fingerprinted Connections',
      icon: faDiagramProject,
      value: data ? rows.length : undefined,
    },
  ];
  return (
    <>
      <section className={styles.metrics} aria-label="Fingerprint statistics">
        {metrics.map((metric) => (
          <div key={metric.title} className={styles.metric}>
            <span className={styles.metricIcon}>
              <FontAwesomeIcon icon={metric.icon} />
            </span>
            <div>
              <p>{metric.title}</p>
              <strong>
                {metric.value === undefined ? '\u2014' : metric.value.toLocaleString()}
              </strong>
            </div>
          </div>
        ))}
      </section>
      <div className={styles.supportStatus} aria-label="Extraction support">
        {kinds.map((kind) => (
          <span
            key={kind}
            data-supported={
              analysis.capabilities[kind]?.supported ||
              analysis.capabilities[kind]?.status === 'extracted'
            }
            title={analysis.capabilities[kind]?.reason}
          >
            {kind.toUpperCase()}:{' '}
            {analysis.capabilities[kind]?.supported ||
            analysis.capabilities[kind]?.status === 'extracted'
              ? 'Supported'
              : (analysis.capabilities[kind]?.status || 'unavailable').replaceAll('_', ' ')}
          </span>
        ))}
        <small>
          Support describes the runtime used for this analysis; values require applicable captured
          traffic.
        </small>
      </div>
      <div className={styles.filters}>
        <label className={styles.search}>
          <FontAwesomeIcon icon={faMagnifyingGlass} />
          <input
            aria-label="Search fingerprints, IP or domain"
            placeholder="Search by fingerprint, IP or domain..."
            value={search}
            onChange={(e) => changeFilter(() => setSearch(e.target.value))}
          />
        </label>
        <label className={styles.filter}>
          <span>Type:</span>
          <select
            aria-label="Fingerprint type"
            value={type}
            onChange={(e) => changeFilter(() => setType(e.target.value))}
          >
            <option value="all">All</option>
            {kinds.map((kind) => (
              <option key={kind} value={kind}>
                {kind.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.filter}>
          <span>Protocol:</span>
          <select
            aria-label="Protocol filter"
            value={service}
            onChange={(e) => changeFilter(() => setService(e.target.value))}
          >
            <option value="all">All</option>
            {services.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label className={styles.filter}>
          <span>Subject:</span>
          <select
            aria-label="Source subject filter"
            value={subject}
            onChange={(e) => changeFilter(() => setSubject(e.target.value))}
          >
            <option value="all">All</option>
            {subjects.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <button
          className={styles.button + ' ' + styles.export}
          type="button"
          disabled={!filtered.length}
          onClick={() => {
            exportCsv(filtered, analysis.filename);
            setNotice(`Exported ${filtered.length} filtered connections.`);
          }}
        >
          <FontAwesomeIcon icon={faArrowUpFromBracket} />
          Export
        </button>
      </div>
      {notice && (
        <p role="status" className={styles.notice}>
          {notice}
        </p>
      )}
      {current?.error && (
        <div role="alert" className={styles.error}>
          {current.error}
          <button className={styles.button} onClick={() => setAttempt(attempt + 1)}>
            Try again
          </button>
        </div>
      )}
      <div className={styles.workspace}>
        <section className={styles.tablePanel} aria-label="Fingerprint connections">
          <div className={styles.tableScroll}>
            <table className={styles.table}>
              <caption className="sr-only">
                Connections with recorded JA4, JA4S or JA4H fingerprints
              </caption>
              <thead>
                <tr>
                  <th aria-sort={ascending ? 'ascending' : 'descending'}>
                    <button
                      type="button"
                      onClick={() => {
                        setAscending(!ascending);
                        setPage(0);
                      }}
                    >
                      Time <span aria-hidden="true">{ascending ? '\u2191' : '\u2193'}</span>
                    </button>
                  </th>
                  <th>Subject (Src IP)</th>
                  <th>Destination (Dst IP)</th>
                  <th>Protocol</th>
                  <th>JA4</th>
                  <th>JA4S</th>
                  <th>JA4H</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr
                    key={row.connection.id}
                    className={
                      selected?.connection.id === row.connection.id ? styles.selected : undefined
                    }
                  >
                    <td>
                      <button
                        type="button"
                        className={styles.rowSelect}
                        onClick={() => setSelectedId(row.connection.id)}
                        aria-label={`Inspect connection from ${row.connection.source} to ${row.connection.destination}`}
                      >
                        {observedTime(row.connection.timestamp)}
                      </button>
                    </td>
                    <td>
                      <button
                        type="button"
                        className={styles.rowSelect}
                        onClick={() => setSelectedId(row.connection.id)}
                      >
                        <FontAwesomeIcon icon={faDesktop} />
                        {row.connection.source}
                      </button>
                    </td>
                    <td>
                      <button
                        type="button"
                        className={styles.rowSelect}
                        onClick={() => setSelectedId(row.connection.id)}
                      >
                        {row.connection.destination}
                      </button>
                    </td>
                    <td>
                      <span
                        className={styles.protocol}
                        data-http={protocol(row.connection).includes('HTTP')}
                      >
                        {protocol(row.connection)}
                      </span>
                    </td>
                    {kinds.map((kind) => (
                      <td key={kind}>
                        <FingerprintValue values={row[kind]} onCopy={(value) => void copy(value)} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!current && (
            <div className={styles.empty} role="status">
              <FontAwesomeIcon icon={faFingerprint} />
              <h2>Loading fingerprint evidence...</h2>
              <p>Reading the selected analysis.</p>
            </div>
          )}
          {data && !rows.length && (
            <div className={styles.empty}>
              <FontAwesomeIcon icon={faFingerprint} />
              <h2>No extracted fingerprints</h2>
              <p>
                This analysis contains no recorded JA4, JA4S or JA4H values. Missing fingerprints do
                not establish that traffic is safe.
              </p>
              <div className={styles.capabilities}>
                {kinds.map((kind) => (
                  <span key={kind} title={analysis.capabilities[kind]?.reason}>
                    {kind.toUpperCase()}:{' '}
                    {(analysis.capabilities[kind]?.status || 'unavailable').replaceAll('_', ' ')}
                  </span>
                ))}
              </div>
              <p className={styles.emptyHint}>
                Extraction requires applicable traffic and a runtime with JA4+ support.
              </p>
            </div>
          )}
          {data && rows.length > 0 && !filtered.length && (
            <div className={styles.empty}>
              <h2>No matching connections</h2>
              <p>Try a different search or reset the filters.</p>
              <button
                className={styles.button}
                onClick={() =>
                  changeFilter(() => {
                    setSearch('');
                    setType('all');
                    setService('all');
                    setSubject('all');
                  })
                }
              >
                Reset filters
              </button>
            </div>
          )}
          <footer className={styles.pagination}>
            <span>
              {filtered.length
                ? `Showing ${actualPage * pageSize + 1}\u2013${Math.min((actualPage + 1) * pageSize, filtered.length)} of ${filtered.length.toLocaleString()} connections`
                : 'Showing 0 connections'}
            </span>
            <nav aria-label="Fingerprint pages">
              <button
                type="button"
                aria-label="Previous page"
                disabled={actualPage === 0}
                onClick={() => setPage(actualPage - 1)}
              >
                <FontAwesomeIcon icon={faChevronLeft} />
              </button>
              {Array.from(
                { length: Math.min(5, pages) },
                (_, i) => Math.min(Math.max(0, actualPage - 2), Math.max(0, pages - 5)) + i,
              ).map((index) => (
                <button
                  key={index}
                  type="button"
                  aria-label={`Page ${index + 1}`}
                  aria-current={index === actualPage ? 'page' : undefined}
                  onClick={() => setPage(index)}
                >
                  {index + 1}
                </button>
              ))}
              <button
                type="button"
                aria-label="Next page"
                disabled={actualPage + 1 >= pages}
                onClick={() => setPage(actualPage + 1)}
              >
                <FontAwesomeIcon icon={faChevronRight} />
              </button>
            </nav>
          </footer>
        </section>
        <aside className={styles.detailPanel} aria-labelledby="fingerprint-details">
          <div className={styles.detailHeading}>
            <h2 id="fingerprint-details">Fingerprint Details</h2>
            {selected && (
              <button
                type="button"
                className={styles.copy}
                aria-label="Close fingerprint details"
                onClick={() => setSelectedId(null)}
              >
                <FontAwesomeIcon icon={faXmark} />
              </button>
            )}
          </div>
          {!selected ? (
            <div className={styles.detailEmpty}>
              <FontAwesomeIcon icon={faDiagramProject} />
              <p>Select a connection to inspect its fingerprints and recorded context.</p>
            </div>
          ) : (
            <>
              <div className={styles.detailMeta}>
                <span
                  className={styles.protocol}
                  data-http={protocol(selected.connection).includes('HTTP')}
                >
                  {protocol(selected.connection)}
                </span>
                <span>{observedTime(selected.connection.timestamp, true)}</span>
              </div>
              <dl className={styles.detailList}>
                <div>
                  <dt>Subject (Src)</dt>
                  <dd>{selected.connection.source}</dd>
                </div>
                <div>
                  <dt>Destination (Dst)</dt>
                  <dd>{selected.connection.destination}</dd>
                </div>
              </dl>
              <div className={styles.fullValues}>
                {kinds.map((kind) => (
                  <div key={kind}>
                    <p>{kind.toUpperCase()}</p>
                    {selected[kind].length ? (
                      selected[kind].map((fp) => (
                        <div key={fp.id}>
                          <code>{fp.value}</code>
                          <button
                            type="button"
                            className={styles.copy}
                            aria-label={`Copy full ${kind.toUpperCase()} value`}
                            onClick={() => void copy(fp.value)}
                          >
                            <FontAwesomeIcon icon={faCopy} />
                          </button>
                        </div>
                      ))
                    ) : (
                      <span className={styles.absent}>Not observed</span>
                    )}
                  </div>
                ))}
              </div>
              <h3 className={styles.contextTitle}>Context</h3>
              <dl className={styles.detailList}>
                <div>
                  <dt>SNI</dt>
                  <dd>{details?.sni || 'Not observed'}</dd>
                </div>
                <div>
                  <dt>User Agent</dt>
                  <dd>{details?.userAgent || 'Not observed'}</dd>
                </div>
                <div>
                  <dt>Domains</dt>
                  <dd>{selected.connection.domains.join(', ') || 'Not observed'}</dd>
                </div>
                <div>
                  <dt>Related connections</dt>
                  <dd>
                    {
                      new Set(
                        kinds.flatMap((kind) => selected[kind].flatMap((fp) => fp.connection_ids)),
                      ).size
                    }
                  </dd>
                </div>
              </dl>
              <details className={styles.sources}>
                <summary>Extraction sources</summary>
                {[
                  ...new Set(kinds.flatMap((kind) => selected[kind].flatMap((fp) => fp.sources))),
                ].map((value) => (
                  <p key={value}>{value}</p>
                ))}
              </details>
              <Link
                className={styles.trafficLink}
                to={`/user/networkTraffic?analysis=${encodeURIComponent(analysis.id)}`}
                onClick={() => selectAnalysis(analysis.id)}
              >
                <FontAwesomeIcon icon={faArrowUpRightFromSquare} />
                View in Network Traffic
              </Link>
            </>
          )}
        </aside>
      </div>
    </>
  );
}
