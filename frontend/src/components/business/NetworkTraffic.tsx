import PageHeader from '../shared/PageHeader';
import PageLayout from '../shared/PageLayout';
import { faNetworkWired } from '@fortawesome/free-solid-svg-icons';

const NetworkTraffic = () => {
  return (
    <PageLayout>
      <PageHeader
        icon={faNetworkWired}
        title="Network Traffic"
        subtitle="Explore captured network connections, inspect traffic flows, and review communication between hosts"
      />
    </PageLayout>
  );
};

export default NetworkTraffic;
