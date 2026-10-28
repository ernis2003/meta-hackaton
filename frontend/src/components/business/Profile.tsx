import PageHeader from '../shared/PageHeader';
import PageLayout from '../shared/PageLayout';
import { faCircleUser } from '@fortawesome/free-solid-svg-icons';

const Profile = () => {
  return (
    <PageLayout>
      <PageHeader icon={faCircleUser} title="Profile" subtitle="View your account information" />
    </PageLayout>
  );
};

export default Profile;
