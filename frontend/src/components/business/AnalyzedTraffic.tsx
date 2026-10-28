import PageHeader from '../shared/PageHeader';
import PageLayout from '../shared/PageLayout';
import { faNetworkWired } from '@fortawesome/free-solid-svg-icons';

const AnalyzedTraffic = () => {
  return (
    <PageLayout>
      <PageHeader
        icon={faNetworkWired}
        title="Analyzed Traffic"
        subtitle="Review analyses across the platform, inspect captured traffic summaries, and investigate detected threats"
      />
    </PageLayout>
  );
};

export default AnalyzedTraffic;
