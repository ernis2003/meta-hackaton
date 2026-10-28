import SideBar from './SideBar';
import MainView from './MainView';

type DashboardType = {
  targetUser: 'user' | 'admin';
  children: React.ReactNode;
  activeTab: string;
};

const Dashboard = ({ targetUser, children, activeTab }: DashboardType) => {
  return (
    <div className="min-h-dvh w-full flex flex-col md:flex-row">
      <SideBar targetUser={targetUser} activeTab={activeTab} />
      <MainView>{children}</MainView>
    </div>
  );
};

export default Dashboard;
