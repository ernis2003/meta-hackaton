import PageHeader from '../shared/PageHeader';
import PageLayout from '../shared/PageLayout';
import { faChartLine } from '@fortawesome/free-solid-svg-icons';

const BehaviorChanges = () => {
  return (
    <PageLayout>
      <PageHeader
        icon={faChartLine}
        title="Behavior Changes"
        subtitle="Compare network behavior over time and investigate changes in traffic patterns, connections, and service usage"
      />
    </PageLayout>
  );
};

export default BehaviorChanges;
