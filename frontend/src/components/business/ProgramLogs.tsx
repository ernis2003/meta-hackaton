import PageHeader from '../shared/PageHeader';
import PageLayout from '../shared/PageLayout';
import { faFileLines } from '@fortawesome/free-solid-svg-icons';

const ProgramLogs = () => {
  return (
    <PageLayout>
      <PageHeader
        icon={faFileLines}
        title="Program logs"
        subtitle="Review application events, authentication activity, and processing errors to monitor platform operation"
      />
    </PageLayout>
  );
};

export default ProgramLogs;
