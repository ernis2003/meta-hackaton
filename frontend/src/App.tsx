import Login from './components/features/auth/Login';
import SignUp from './components/features/auth/Signup';
import Dashboard from './components/global/Dashboard';
import './App.css';
import { useState, type ComponentType } from 'react';
import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom';
import UploadFile from './components/business/UploadFile';
import Profile from './components/business/Profile';
import AnalysisHistory from './components/business/AnalysisHistory';
import Anomalies from './components/business/Anomalies';
import NetworkTraffic from './components/business/NetworkTraffic';
import Fingerprints from './components/business/Fingerprints';
import NetworkSubjects from './components/business/NetworkSubjects';
import PeriodicActivity from './components/business/PeriodicActivity';
import BehaviorChanges from './components/business/BehaviorChanges';
import UserManagement from './components/business/UserManagement';
import AnalyzedTraffic from './components/business/AnalyzedTraffic';
import ProgramLogs from './components/business/ProgramLogs';
import { adminSideBarStructure, userSideBarStructure } from './data/sidebar';

const userPages: Record<string, ComponentType> = {
  'PCAP Analysis': UploadFile,
  'Network Traffic': NetworkTraffic,
  'JA4+ Fingerprints': Fingerprints,
  'Network Subjects': NetworkSubjects,
  Anomalies,
  'Periodic Activity': PeriodicActivity,
  'Behavior Changes': BehaviorChanges,
  'Analysis History': AnalysisHistory,
  Profile,
};

const adminPages: Record<string, ComponentType> = {
  'User management': UserManagement,
  'Analyzed Traffic': AnalyzedTraffic,
  'Program logs': ProgramLogs,
  Profile,
};

function DashboardPage({
  role,
  title,
  page: Page,
}: {
  role: 'user' | 'admin';
  title: string;
  page: ComponentType;
}) {
  const currentRole = sessionStorage.getItem('user_role') === 'admin' ? 'admin' : 'user';
  if (currentRole !== role) {
    return (
      <Navigate to={currentRole === 'admin' ? '/admin/getUsers' : '/user/dashboard'} replace />
    );
  }
  return (
    <Dashboard targetUser={role} activeTab={title}>
      <Page />
    </Dashboard>
  );
}

function App() {
  const [loginAdmin, setloginAdmin] = useState(
    () => sessionStorage.getItem('user_role') === 'admin',
  );

  return (
    <div className="root">
      <BrowserRouter>
        <Routes>
          <Route
            path="/"
            element={<Login loginAdmin={loginAdmin} setloginAdmin={setloginAdmin} />}
          />
          <Route path="/signup" element={<SignUp onAuthenticated={setloginAdmin} />} />
          {Object.entries(userSideBarStructure).map(([title, [, path]]) => {
            const Page = userPages[title];
            return (
              <Route
                key={path}
                path={path}
                element={<DashboardPage role="user" title={title} page={Page} />}
              />
            );
          })}
          {Object.entries(adminSideBarStructure).map(([title, [, path]]) => {
            const Page = adminPages[title];
            return (
              <Route
                key={path}
                path={path}
                element={<DashboardPage role="admin" title={title} page={Page} />}
              />
            );
          })}
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
