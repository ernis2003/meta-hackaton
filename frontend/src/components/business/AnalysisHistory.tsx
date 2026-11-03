import { Link } from 'react-router-dom';
import { selectAnalysis } from '../../utils/analyses';
import AnalysisList from './AnalysisList';
import EvidenceDetails from './EvidenceDetails';

const resultLinks = [
  ['Open graph', '/user/networkSubjects'], ['Anomalies', '/user/anomalies'],
  ['Fingerprints', '/user/fingerprints'], ['Traffic', '/user/networkTraffic'],
];

export default function AnalysisHistory() {
  return <AnalysisList title="Analysis History">{analysis => <>
    <EvidenceDetails record={{
      uploaded_at: new Date(analysis.uploaded_at).toLocaleString(),
      processing_duration: analysis.duration_seconds == null ? 'Not available' : `${analysis.duration_seconds.toFixed(2)} s`,
      ...(analysis.error ? {error: analysis.error} : {}),
      ...Object.fromEntries(Object.entries(analysis.summary).filter(([key]) => key !== 'connections')),
    }} />
    <div className="mt-5 flex flex-wrap gap-3">
      {resultLinks.map(([label, path]) => <Link key={path}
        to={`${path}?analysis=${encodeURIComponent(analysis.id)}`} onClick={() => selectAnalysis(analysis.id)}
        className="rounded-md bg-[#2B3849] px-3 py-2 text-sm hover:bg-[#35465B] focus-visible:outline-2 focus-visible:outline-[#3FDDBB]">
        {label}
      </Link>)}
    </div>
  </>}</AnalysisList>;
}
