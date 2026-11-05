import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, selectAnalysis, type Analysis, type Page, type Result } from '../../utils/analyses';
import AnalysisList from './AnalysisList';
import EvidenceDetails from './EvidenceDetails';
import AIInvestigation from './AIInvestigation';

type ResultsProps = {kind: string; title: string; filter?: string[]};
export default function AnalysisResults(props: ResultsProps) {
  return <AnalysisList title={props.title}>{analysis => <ResultsView {...props} analysis={analysis} />}</AnalysisList>;
}
function ResultsView({kind, filter, analysis}: ResultsProps & {analysis: Analysis}) {
  const [data, setData] = useState<Page<Result>>();
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true); setError('');
    api<Page<Result>>(`/${analysis.id}/${kind}?limit=25&offset=${offset}&anomaly_type=${encodeURIComponent(filter?.join(',') || '')}`)
      .then(value => { if (active) setData(value); })
      .catch(e => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [analysis.id, kind, offset, filter]);
  return <div className="flex flex-col gap-4">
    <EvidenceDetails record={Object.fromEntries(Object.entries(analysis.summary).filter(([key]) => key.endsWith('_count') || ['ip_bytes', 'packets'].includes(key)))} />
    {kind === 'fingerprints' && Object.entries(analysis.capabilities).map(([k, v]) => <p key={k} className="text-sm text-slate-400">{k.toUpperCase()}: {v.status} — {v.reason}</p>)}
    {loading && <p role="status">Loading results...</p>}
    {error && <p role="alert" className="text-red-300">{error}</p>}
    {!loading && !error && data && <>
      {!data.items.length && <p className="text-slate-400">No matching records for this analysis.</p>}
      {data.items.map(item => <article className="rounded-xl border border-slate-700 p-4" key={item.id}>
        {kind === 'anomalies' && <Link className="mb-3 inline-block text-teal-300"
          onClick={() => selectAnalysis(analysis.id)}
          to={`/user/networkSubjects?analysis=${encodeURIComponent(analysis.id)}&focus=${encodeURIComponent(String((item.subject_ids as string[])?.[0] || ''))}`}>Focus related hosts</Link>}
        <EvidenceDetails record={item} />
        {kind === 'anomalies' && <AIInvestigation analysisId={analysis.id} anomalyId={item.id} />}
      </article>)}
      {data.total > 25 && <div className="flex items-center gap-4 text-sm">
        <button disabled={!offset} className="rounded-md bg-[#2B3849] px-3 py-2 disabled:opacity-40" onClick={() => setOffset(Math.max(0, offset - 25))}>Previous</button>
        <span className="text-slate-400">{offset + 1}-{Math.min(offset + 25, data.total)} / {data.total}</span>
        <button disabled={offset + 25 >= data.total} className="rounded-md bg-[#2B3849] px-3 py-2 disabled:opacity-40" onClick={() => setOffset(offset + 25)}>Next</button>
      </div>}
    </>}
  </div>;
}
