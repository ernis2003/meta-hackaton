import AnalysisResults from './AnalysisResults';
const filter = ['periodic_communication'];
export default function PeriodicActivity() { return <AnalysisResults kind="anomalies" title="Periodic Activity" filter={filter} />; }
