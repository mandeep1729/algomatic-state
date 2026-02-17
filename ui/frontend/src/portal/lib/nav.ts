/**
 * Navigation configuration for the app portal sidebar.
 */

export interface NavItem {
  path: string;
  label: string;
  icon: string;
  children?: NavItem[];
}

export const appNavSections: NavItem[] = [
  {
    path: '/app',
    label: 'Overview',
    icon: 'LayoutDashboard',
  },
  {
    path: '/app/dashboard',
    label: 'Dashboard',
    icon: 'BarChart3',
  },
  {
    path: '/app/insights',
    label: 'Insights',
    icon: 'TrendingUp',
  },
  {
    path: '/app/campaigns',
    label: 'Campaigns',
    icon: 'ArrowRightLeft',
  },
  {
    path: '/app/transactions',
    label: 'Transactions',
    icon: 'Receipt',
  },
  {
    path: '/app/strategy-probe',
    label: 'Strategy Probe',
    icon: 'Target',
  },
  {
    path: '/app/evaluate',
    label: 'Evaluate',
    icon: 'Search',
  },
  {
    path: '/app/settings',
    label: 'Settings',
    icon: 'Settings',
    children: [
      {
        path: '/app/settings/profile',
        label: 'Profile',
        icon: 'User',
      },
      {
        path: '/app/settings/risk',
        label: 'Risk',
        icon: 'Shield',
      },
      {
        path: '/app/settings/strategies',
        label: 'Strategies',
        icon: 'Target',
      },
      {
        path: '/app/settings/brokers',
        label: 'Brokers',
        icon: 'Link',
      },
      {
        path: '/app/settings/evaluation-controls',
        label: 'Evaluation',
        icon: 'Sliders',
      },
      {
        path: '/app/settings/data-privacy',
        label: 'Data & Privacy',
        icon: 'Lock',
      },
    ],
  },
];
