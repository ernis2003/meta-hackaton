import { useEffect, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faChevronRight } from '@fortawesome/free-solid-svg-icons';
import { api, selectAnalysis, type Analysis, type Page } from '../../utils/analyses';
import PageLayout from '../shared/PageLayout';

const PAGE_SIZE = 25;

function AnalysisRow({analysis, initiallyOpen, children}: {
  analysis: Analysis; initiallyOpen: boolean; children: (analysis: Analysis) => ReactNode;
}) {
  const [expanded, setExpanded] = useState(initiallyOpen);
  return <details open={expanded}
    onToggle={e => {
      const open = e.currentTarget.open;
      setExpanded(open);
      if (open) selectAnalysis(analysis.id);
    }}
    className="group/analysis overflow-hidden rounded-xl border border-slate-700 bg-[#1C2633]">
    <summary className="flex cursor-pointer list-none items-center gap-4 p-4 hover:bg-[#243142] focus-visible:outline-2 focus-visible:outline-[#3FDDBB] [&::-webkit-details-marker]:hidden">
      <FontAwesomeIcon icon={faChevronRight} className="shrink-0 text-sm text-slate-400 transition-transform group-open/analysis:rotate-90" />
      <span className="min-w-0 flex-1 break-words font-medium">{analysis.filename}</span>
      <span className={`shrink-0 rounded-md px-2 py-1 text-xs capitalize ${analysis.status === 'completed' ? 'bg-teal-400/10 text-teal-300' : analysis.status === 'failed' ? 'bg-red-400/10 text-red-300' : 'bg-blue-400/10 text-blue-300'}`}>
        {analysis.status}
      </span>
      <time dateTime={analysis.uploaded_at} className="hidden shrink-0 text-sm text-slate-400 sm:block">
        {new Date(analysis.uploaded_at).toLocaleString()}
      </time>
    </summary>
    {expanded && <div className="border-t border-slate-700 p-4 sm:p-5">
      {analysis.status === 'completed' ? children(analysis) : <p role="status" className="text-sm text-slate-400">
        {analysis.error || 'Analysis is still processing. Results will be available when it completes.'}
      </p>}
    </div>}
  </details>;
}

export default function AnalysisList({title, children}: {title: string; children: (analysis: Analysis) => ReactNode}) {
  const [params] = useSearchParams();
  const requestedId = params.get('analysis') || '';
  const [data, setData] = useState<Page<Analysis>>();
  const [requested, setRequested] = useState<Analysis>();
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setLoading(true); setError('');
    Promise.all([api<Page<Analysis>>(`?limit=${PAGE_SIZE}&offset=${offset}`),
      requestedId ? api<Analysis>(`/${encodeURIComponent(requestedId)}`) : Promise.resolve(undefined)])
      .then(([page, selected]) => { if (active) { setData(page); setRequested(selected); } })
      .catch(e => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [offset, requestedId]);
  const items = data ? requested && !data.items.some(a => a.id === requested.id)
    ? [requested, ...data.items] : data.items : [];
  return <PageLayout>
    <h1 className="text-2xl">{title}</h1>
    {loading && <p role="status">Loading analyses...</p>}
    {error && <p role="alert" className="text-red-300">{error}</p>}
    {!loading && !error && data && <>
      {!items.length && <p className="text-slate-400">No analyses yet. Upload a PCAP file to begin.</p>}
      <div className="flex flex-col gap-3">
        {items.map(analysis => <AnalysisRow key={`${analysis.id}:${requestedId}`} analysis={analysis} initiallyOpen={analysis.id === requestedId}>
          {children}
        </AnalysisRow>)}
      </div>
      {data.total > PAGE_SIZE && <nav aria-label={`${title} pages`} className="flex items-center gap-4 text-sm">
        <button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          className="rounded-md bg-[#2B3849] px-3 py-2 disabled:opacity-40">Previous</button>
        <span className="text-slate-400">{offset + 1}-{Math.min(offset + PAGE_SIZE, data.total)} / {data.total}</span>
        <button disabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}
          className="rounded-md bg-[#2B3849] px-3 py-2 disabled:opacity-40">Next</button>
      </nav>}
    </>}
  </PageLayout>;
}
