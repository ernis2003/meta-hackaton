import { useEffect, useState } from 'react';
import { api } from '../../utils/analyses';

export const bytes = (value: unknown) => {
  const n = Number(value) || 0;
  const unit = n > 0 ? Math.min(3, Math.floor(Math.log(n) / Math.log(1024))) : 0;
  return `${(n / 1024 ** unit).toLocaleString(undefined, { maximumFractionDigits: 1 })} ${['B', 'KB', 'MB', 'GB'][unit]}`;
};
export const timeLabel = (value: unknown) =>
  value == null ? 'Not recorded' : new Date(Number(value) * 1000).toLocaleString();
export function Metric({
  label,
  value,
  accent = 'text-white',
}: {
  label: string;
  value: React.ReactNode;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-700/70 bg-[#131e2c] p-4">
      <p className="text-xs uppercase tracking-wider text-slate-400">{label}</p>
      <p className={`mt-2 text-xl font-semibold ${accent}`}>{value}</p>
    </div>
  );
}
type Bucket = { timestamp: number; sent: number; received: number; connections: number };
type Activity = {
  subject: {
    ip_address: string;
    first_seen: number | null;
    last_seen: number | null;
    bytes_sent: number;
    bytes_received: number;
    total_connections: number;
    protocols: string[];
  };
  buckets: Bucket[];
  interval_seconds: number;
  total_connections: number;
  untimed_connections: number;
  peers: { ip: string; sent: number; received: number; connections: number }[];
  connections: {
    id: string;
    timestamp: number | null;
    last_seen: number | null;
    peer: string;
    subject_sent: number;
    subject_received: number;
    destination_port: number;
    protocols: string[];
  }[];
};
export default function SubjectActivity({
  analysisId,
  subjectId,
  compact = false,
}: {
  analysisId: string;
  subjectId: string;
  compact?: boolean;
}) {
  const [data, setData] = useState<Activity>();
  const [error, setError] = useState('');
  const [hover, setHover] = useState<number>();
  useEffect(() => {
    let active = true;
    setData(undefined);
    setError('');
    setHover(undefined);
    api<Activity>(`/${analysisId}/activity/${encodeURIComponent(subjectId)}`)
      .then((value) => {
        if (active) setData(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [analysisId, subjectId]);
  if (error)
    return (
      <p role="alert" className="text-red-300">
        {error}
      </p>
    );
  if (!data)
    return (
      <p role="status" className="py-6 text-slate-400">
        Loading subject activity…
      </p>
    );
  const max = Math.max(1, ...data.buckets.map((b) => Math.max(b.sent, b.received)));
  const active = hover === undefined ? undefined : data.buckets[hover];
  const maxPeer = Math.max(1, ...data.peers.map((p) => p.sent + p.received));
  return (
    <div className="space-y-5">
      <div className={`grid gap-3 ${compact ? 'grid-cols-2' : 'grid-cols-2 lg:grid-cols-4'}`}>
        <Metric label="Sent ↑" value={bytes(data.subject.bytes_sent)} accent="text-teal-300" />
        <Metric
          label="Received ↓"
          value={bytes(data.subject.bytes_received)}
          accent="text-blue-300"
        />
        <Metric label="Connections" value={data.total_connections.toLocaleString()} />
        <Metric
          label="Protocols"
          value={data.subject.protocols.join(' / ').toUpperCase() || 'Unknown'}
        />
      </div>
      <div className="rounded-xl border border-slate-700 bg-[#101a28] p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium">Traffic over time</h3>
          <span className="text-xs text-slate-400">
            <span className="text-teal-300">● Sent</span>　
            <span className="text-blue-300">● Received</span>
          </span>
        </div>
        <p className="mt-1 text-xs text-slate-400">
          Connection totals grouped by start time · {Math.round(data.interval_seconds)}s intervals
        </p>
        {data.buckets.length ? (
          <>
            <div className="mt-4 flex justify-between text-xs text-slate-500">
              <span>{bytes(max)} / interval</span>
              <span>Hover or focus a time interval</span>
            </div>
            <svg
              viewBox="0 0 800 180"
              className="mt-2 w-full"
              role="img"
              aria-label="Sent and received bytes per time interval"
            >
              {[0, 1, 2, 3].map((i) => (
                <line
                  key={i}
                  x1="0"
                  x2="800"
                  y1={i * 50 + 10}
                  y2={i * 50 + 10}
                  stroke="#263347"
                  strokeDasharray="4 5"
                />
              ))}
              {data.buckets.map((b, i) => (
                <g
                  key={b.timestamp}
                  tabIndex={0}
                  role="button"
                  aria-label={`${timeLabel(b.timestamp)}: ${bytes(b.sent)} sent, ${bytes(b.received)} received, ${b.connections} connections`}
                  onFocus={() => setHover(i)}
                  onMouseEnter={() => setHover(i)}
                >
                  <rect
                    x={i * 25}
                    y="0"
                    width="25"
                    height="180"
                    fill={hover === i ? '#ffffff0e' : 'transparent'}
                  />
                  <rect
                    x={i * 25 + 3}
                    y={170 - (b.sent / max) * 150}
                    width="8"
                    height={(b.sent / max) * 150}
                    rx="2"
                    fill="#3fddbb"
                  />
                  <rect
                    x={i * 25 + 13}
                    y={170 - (b.received / max) * 150}
                    width="8"
                    height={(b.received / max) * 150}
                    rx="2"
                    fill="#6d98e3"
                  />
                  <title>
                    {timeLabel(b.timestamp)}: ↑ {bytes(b.sent)} · ↓ {bytes(b.received)} ·{' '}
                    {b.connections} connections
                  </title>
                </g>
              ))}
            </svg>
            <div className="flex justify-between gap-3 text-xs text-slate-400">
              <span>{timeLabel(data.buckets[0].timestamp)}</span>
              <span>{timeLabel(data.buckets.at(-1)!.timestamp + data.interval_seconds)}</span>
            </div>
            <p className="mt-3 min-h-5 text-sm text-slate-300" aria-live="polite">
              {active
                ? `${timeLabel(active.timestamp)} · ↑ ${bytes(active.sent)} · ↓ ${bytes(active.received)} · ${active.connections} connections`
                : 'Select an interval to inspect its traffic.'}
            </p>
          </>
        ) : (
          <p className="py-6 text-slate-400">No recorded timestamps for this subject.</p>
        )}
        {data.untimed_connections > 0 && (
          <p className="text-xs text-amber-300">
            {data.untimed_connections} connections have no timestamp and are excluded from this
            chart.
          </p>
        )}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-700 p-4">
          <h3 className="mb-3 font-medium">Observed activity window</h3>
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-slate-400">First seen</dt>
              <dd>{timeLabel(data.subject.first_seen)}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Last seen</dt>
              <dd>{timeLabel(data.subject.last_seen)}</dd>
            </div>
          </dl>
        </div>
        <div className="rounded-xl border border-slate-700 p-4">
          <h3 className="mb-3 font-medium">Top communication partners</h3>
          <div className="max-h-60 space-y-4 overflow-auto">
            {data.peers.map((peer) => (
              <div key={peer.ip}>
                <div className="mb-1 flex justify-between gap-2 text-xs">
                  <span className="font-mono">{peer.ip}</span>
                  <span className="text-slate-400">
                    {peer.connections} sessions · {bytes(peer.sent + peer.received)}
                  </span>
                </div>
                <div className="flex h-2 overflow-hidden rounded bg-slate-800">
                  <div
                    className="bg-teal-300"
                    style={{ width: `${(peer.sent / maxPeer) * 100}%` }}
                  />
                  <div
                    className="bg-blue-400"
                    style={{ width: `${(peer.received / maxPeer) * 100}%` }}
                  />
                </div>
              </div>
            ))}
            {!data.peers.length && (
              <p className="text-sm text-slate-400">No communication partners recorded.</p>
            )}
          </div>
        </div>
      </div>
      {!compact && (
        <div className="overflow-x-auto rounded-xl border border-slate-700">
          <div className="p-4">
            <h3 className="font-medium">Connection timeline</h3>
            <p className="text-xs text-slate-400">
              Latest {data.connections.length} of {data.total_connections} connections · bytes
              relative to this subject
            </p>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-800/60 text-xs text-slate-400">
              <tr>
                {['Started', 'Partner', 'Port / protocol', 'Sent ↑', 'Received ↓', 'Duration'].map(
                  (h) => (
                    <th key={h} className="px-4 py-3">
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {data.connections.map((c) => (
                <tr key={c.id} className="border-t border-slate-800 hover:bg-slate-800/40">
                  <td className="px-4 py-3 whitespace-nowrap">{timeLabel(c.timestamp)}</td>
                  <td className="px-4 py-3 font-mono">{c.peer}</td>
                  <td className="px-4 py-3">
                    {c.destination_port ?? '—'} / {c.protocols.join(', ')}
                  </td>
                  <td className="px-4 py-3 text-teal-300">{bytes(c.subject_sent)}</td>
                  <td className="px-4 py-3 text-blue-300">{bytes(c.subject_received)}</td>
                  <td className="px-4 py-3">
                    {c.last_seen != null && c.timestamp != null
                      ? `${Math.max(0, c.last_seen - c.timestamp).toFixed(2)}s`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
