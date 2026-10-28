import PageHeader from '../shared/PageHeader';
import PageLayout from '../shared/PageLayout';
import { faRepeat } from '@fortawesome/free-solid-svg-icons';

const PeriodicActivity = () => {
  return (
    <PageLayout>
      <PageHeader
        icon={faRepeat}
        title="Periodic Activity"
        subtitle="Review recurring connections and repeated traffic patterns to investigate potential beaconing and automated activity"
      />
    </PageLayout>
  );
};

export default PeriodicActivity;
