import PageLayout from '../shared/PageLayout';
import PageHeader from '../shared/PageHeader';
import { faClockRotateLeft } from '@fortawesome/free-solid-svg-icons';

const AnalysisHistory = () => {
  return (
    <PageLayout>
      <PageHeader
        icon={faClockRotateLeft}
        title="Analysis History"
        subtitle="Browse previous PCAP analyses, review results, and revisit detected network threats"
      />
    </PageLayout>
  );
};

export default AnalysisHistory;
