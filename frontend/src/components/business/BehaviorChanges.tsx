import AnalysisResults from './AnalysisResults';
const filter = ['new_fingerprint', 'new_destination'];
export default function BehaviorChanges() { return <AnalysisResults kind="anomalies" title="Behavior Changes" filter={filter} />; }
