import PageHeader from '../shared/PageHeader';
import PageLayout from '../shared/PageLayout';
import { faTriangleExclamation } from '@fortawesome/free-solid-svg-icons';

const Anomalies = () => {
  return (
    <PageLayout>
      <PageHeader
        icon={faTriangleExclamation}
        title="Anomalies"
        subtitle="Explore detected network anomalies and investigate potential security threats"
      />
    </PageLayout>
  );
};

export default Anomalies;
