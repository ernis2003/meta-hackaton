import PageHeader from '../shared/PageHeader';
import PageLayout from '../shared/PageLayout';
import { faUserGear } from '@fortawesome/free-solid-svg-icons';

const UserManagement = () => {
  return (
    <PageLayout>
      <PageHeader
        icon={faUserGear}
        title="User management"
        subtitle="Review registered accounts, manage user roles, and control access to the analysis platform"
      />
    </PageLayout>
  );
};

export default UserManagement;
