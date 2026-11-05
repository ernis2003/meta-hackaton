import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AnalysisList from './AnalysisList';
import SubjectActivity, { bytes } from './SubjectActivity';
import { api, type Page, type Result } from '../../utils/analyses';
import EvidenceDetails from './EvidenceDetails';

export default function BehaviorChanges() {
  return (
    <AnalysisList title="Behavior Changes">
      {(analysis) => <BehaviorView key={analysis.id} id={analysis.id} />}
    </AnalysisList>
  );
}
function BehaviorView({ id }: { id: string }) {
  const [subjects, setSubjects] = useState<Page<Result>>();
  const [selected, setSelected] = useState('');
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [changes, setChanges] = useState<Page<Result>>();
  const [changeOffset, setChangeOffset] = useState(0);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setError('');
    setSubjects(undefined);
    api<Page<Result>>(`/${id}/subjects?limit=50&offset=${offset}`)
      .then((value) => {
        if (active) {
          setSubjects(value);
          setSelected(value.items[0]?.id || '');
          setChangeOffset(0);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [id, offset]);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setChanges(undefined);
    api<Page<Result>>(
      `/${id}/anomalies?subject_id=${encodeURIComponent(selected)}&anomaly_type=new_fingerprint,new_destination&limit=25&offset=${changeOffset}`,
    )
      .then((value) => {
        if (active) setChanges(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [id, selected, changeOffset]);
  const subject = subjects?.items.find((s) => s.id === selected);
  const visible = subjects?.items.filter((s) => String(s.ip_address).includes(search));
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Subject activity explorer</h2>
        <p className="mt-1 text-sm text-slate-400">
          Explore when an address communicates, its traffic volume and observed changes against
          earlier captures.
        </p>
      </div>
      {error && (
        <p role="alert" className="text-red-300">
          {error}
        </p>
      )}
      {!subjects && !error && <p role="status">Loading subjects…</p>}
      {subjects && !subjects.total && (
        <p className="text-slate-400">No subjects were recorded in this capture.</p>
      )}
      {subjects && subjects.total > 0 && (
        <div className="grid items-start gap-5 xl:grid-cols-[260px_minmax(0,1fr)]">
          <aside className="rounded-xl border border-slate-700 bg-[#101a28] p-3">
            <label
              className="mb-2 block text-xs uppercase tracking-wider text-slate-400"
              htmlFor={`subject-search-${id}`}
            >
              Subjects · {subjects.total}
            </label>
            <input
              id={`subject-search-${id}`}
              className="mb-3 w-full rounded-lg border border-slate-700 bg-slate-800 p-2 text-sm"
              placeholder="Filter this page by IP…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <div className="max-h-[620px] space-y-2 overflow-auto">
              {visible?.map((s) => (
                <button
                  key={s.id}
                  onClick={() => {
                    setSelected(s.id);
                    setChangeOffset(0);
                  }}
                  className={`w-full rounded-lg border p-3 text-left transition ${selected === s.id ? 'border-teal-400/70 bg-teal-400/10' : 'border-slate-700/60 hover:bg-slate-800'}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-sm">{String(s.ip_address)}</span>
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${Number(s.anomaly_count) ? 'bg-amber-400' : 'bg-teal-400'}`}
                    />
                  </div>
                  <p className="mt-2 text-xs text-slate-400">
                    {String(s.total_connections)} sessions ·{' '}
                    {bytes(Number(s.bytes_sent) + Number(s.bytes_received))}
                  </p>
                </button>
              ))}
              {!visible?.length && (
                <p className="p-2 text-sm text-slate-400">No matching subjects on this page.</p>
              )}
            </div>
            {subjects.total > 50 && (
              <div className="mt-3 flex justify-between text-sm">
                <button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>
                  Previous
                </button>
                <span>
                  {offset + 1}–{Math.min(offset + 50, subjects.total)}
                </span>
                <button
                  disabled={offset + 50 >= subjects.total}
                  onClick={() => setOffset(offset + 50)}
                >
                  Next
                </button>
              </div>
            )}
          </aside>
          <section className="min-w-0 space-y-5">
            {subject && (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-wider text-teal-300">
                      Selected subject
                    </p>
                    <h2 className="mt-1 font-mono text-2xl">{String(subject.ip_address)}</h2>
                  </div>
                  <Link
                    className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-teal-300"
                    to={`/user/networkSubjects?analysis=${id}&focus=${encodeURIComponent(selected)}`}
                  >
                    View relationships ↗
                  </Link>
                </div>
                <SubjectActivity key={selected} analysisId={id} subjectId={selected} />
                <div className="rounded-xl border border-slate-700 p-4">
                  <h3 className="font-medium">
                    Behavior changes{' '}
                    <span className="ml-2 rounded-full bg-amber-400/10 px-2 py-1 text-xs text-amber-300">
                      {changes?.total ?? '…'}
                    </span>
                  </h3>
                  <p className="mt-1 text-xs text-slate-400">
                    New destinations and fingerprints compared with the available historical
                    baseline.
                  </p>
                  {!changes && (
                    <p className="mt-4 text-sm" role="status">
                      Loading changes…
                    </p>
                  )}
                  {changes?.items.map((c) => (
                    <details key={c.id} className="mt-3 rounded-lg border border-slate-700 p-3">
                      <summary className="cursor-pointer text-sm text-amber-200">
                        {String(c.type).replaceAll('_', ' ')} · {String(c.severity || 'observed')}
                      </summary>
                      <EvidenceDetails record={c} />
                    </details>
                  ))}
                  {changes && !changes.total && (
                    <p className="mt-4 text-sm text-slate-400">
                      No new destinations or fingerprints were flagged for this subject. A
                      historical baseline is required to detect changes.
                    </p>
                  )}
                  {changes && changes.total > 25 && (
                    <div className="mt-3 flex gap-4 text-sm">
                      <button
                        disabled={!changeOffset}
                        onClick={() => setChangeOffset(Math.max(0, changeOffset - 25))}
                      >
                        Previous changes
                      </button>
                      <button
                        disabled={changeOffset + 25 >= changes.total}
                        onClick={() => setChangeOffset(changeOffset + 25)}
                      >
                        More changes
                      </button>
                    </div>
                  )}
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
