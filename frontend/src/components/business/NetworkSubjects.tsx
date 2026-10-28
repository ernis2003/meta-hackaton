import PageHeader from '../shared/PageHeader';
import PageLayout from '../shared/PageLayout';
import { faServer } from '@fortawesome/free-solid-svg-icons';

const NetworkSubjects = () => {
  return (
    <PageLayout>
      <PageHeader
        icon={faServer}
        title="Network Subjects"
        subtitle="Explore hosts, IP addresses, and services observed in captures and investigate their network activity"
      />
    </PageLayout>
  );
};

export default NetworkSubjects;
