import {
  faCircleUser,
  faNetworkWired,
  faUserGear,
  faFileLines,
  faFileImport,
  faFingerprint,
  faServer,
  faTriangleExclamation,
  faClockRotateLeft,
  faChartLine,
  faRepeat,
} from '@fortawesome/free-solid-svg-icons';

import type { IconDefinition } from '@fortawesome/free-solid-svg-icons';
// "Item name": "icon_url", "target URL path when user clicks item", functionToCall

type SidebarItemType = [IconDefinition, string];
type SidebarStructureType = Record<string, SidebarItemType>;

const adminSideBarStructure: SidebarStructureType = {
  'User management': [faUserGear, '/admin/getUsers'],
  'Analyzed Traffic': [faNetworkWired, '/admin/analyzeTraffic'],
  'Program logs': [faFileLines, '/admin/logs'],
  Profile: [faCircleUser, '/admin/profile'],
};

const userSideBarStructure: SidebarStructureType = {
  'PCAP Analysis': [faFileImport, '/user/dashboard'],
  'Network Traffic': [faNetworkWired, '/user/networkTraffic'],
  'JA4+ Fingerprints': [faFingerprint, '/user/fingerprints'],
  'Network Subjects': [faServer, '/user/networkSubjects'],
  Anomalies: [faTriangleExclamation, '/user/anomalies'],
  'Periodic Activity': [faRepeat, '/user/periodicActivity'],
  'Behavior Changes': [faChartLine, '/user/behaviorChanges'],
  'Analysis History': [faClockRotateLeft, '/user/analysisHistory'],
  Profile: [faCircleUser, '/user/profile'],
};

export { adminSideBarStructure, userSideBarStructure };
