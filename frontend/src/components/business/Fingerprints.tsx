import PageHeader from '../shared/PageHeader';
import PageLayout from '../shared/PageLayout';
import { faFingerprint } from '@fortawesome/free-solid-svg-icons';

const Fingerprints = () => {
  return (
    <PageLayout>
      <PageHeader
        icon={faFingerprint}
        title="JA4+ Fingerprints"
        subtitle="Browse JA4+ fingerprints to identify network clients, compare connection signatures, and investigate suspicious patterns"
      />
    </PageLayout>
  );
};

export default Fingerprints;
