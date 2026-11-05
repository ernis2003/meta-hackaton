export function displayValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return 'Not observed';
  if (['timestamp', 'first_seen', 'last_seen'].includes(key) && typeof value === 'number') return new Date(value * 1000).toISOString();
  if (Array.isArray(value)) return value.length ? value.slice(0, 100).map(v => typeof v === 'object' ? JSON.stringify(v) : String(v)).join(', ') + (value.length > 100 ? ` … (${value.length} total)` : '') : 'None observed';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
export default function EvidenceDetails({record}: {record: Record<string, unknown>}) {
  return <dl className="grid grid-cols-[minmax(100px,1fr)_minmax(0,2fr)] gap-x-4 gap-y-2 text-sm">
    {Object.entries(record).filter(([key]) => key !== 'evidence').map(([key, value]) => <div className="contents" key={key}>
      <dt className="text-slate-400 capitalize">{key.replaceAll('_', ' ')}</dt>
      <dd className="break-words min-w-0">{displayValue(key, value)}</dd>
    </div>)}
    {record.evidence != null && <div className="col-span-2"><details><summary>Source evidence</summary>
      <pre className="whitespace-pre-wrap break-all text-xs mt-2">{JSON.stringify(record.evidence, null, 2)}</pre>
    </details></div>}
  </dl>;
}
