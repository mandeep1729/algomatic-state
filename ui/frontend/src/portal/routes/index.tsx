import { createBrowserRouter } from 'react-router-dom';

// Layouts
import RootLayout from '../layouts/RootLayout';
import AppLayout from '../layouts/AppLayout';
import { ChartProvider } from '../context/ChartContext';
import PublicLayout from '../layouts/PublicLayout';
import OnboardingLayout from '../layouts/OnboardingLayout';

// Auth
import Login from '../pages/auth/Login';
import ProtectedRoute from '../components/ProtectedRoute';

// App pages
import Overview from '../pages/app/Overview';
import Trades from '../pages/app/Trades';
import TradeDetail from '../pages/app/TradeDetail';
import Transactions from '../pages/app/Transactions';
import Campaigns from '../pages/app/Campaigns';
import CampaignDetail from '../pages/app/CampaignDetail';
import EvaluateIdea from '../pages/app/EvaluateIdea';
import Insights from '../pages/app/Insights';
import Journal from '../pages/app/Journal';

// Settings pages
import SettingsProfile from '../pages/app/settings/Profile';
import SettingsRisk from '../pages/app/settings/Risk';
import SettingsStrategies from '../pages/app/settings/Strategies';
import SettingsBrokers from '../pages/app/settings/Brokers';
import SettingsEvaluationControls from '../pages/app/settings/EvaluationControls';
import SettingsDataPrivacy from '../pages/app/settings/DataPrivacy';

// Public pages
import Home from '../pages/public/Home';
import HowItWorks from '../pages/public/HowItWorks';
import WhatWeEvaluate from '../pages/public/WhatWeEvaluate';
import WhatWeDontDo from '../pages/public/WhatWeDontDo';
import Pricing from '../pages/public/Pricing';
import FAQ from '../pages/public/FAQ';
import About from '../pages/public/About';
import Disclaimer from '../pages/public/legal/Disclaimer';
import Terms from '../pages/public/legal/Terms';
import Privacy from '../pages/public/legal/Privacy';

// Help pages
import HelpIndex from '../pages/help/HelpIndex';
import HelpEvaluations from '../pages/help/Evaluations';
import HelpBehavioral from '../pages/help/BehavioralSignals';
import HelpWhyFlags from '../pages/help/WhyFlags';
import HelpMisunderstandings from '../pages/help/CommonMisunderstandings';
import HelpContact from '../pages/help/Contact';

// Placeholder for pages not yet built
import Placeholder from '../pages/Placeholder';

// Onboarding placeholders
const OnboardingWelcome = () => <Placeholder title="Welcome" description="Let's set up your trading profile." />;
const OnboardingProfile = () => <Placeholder title="Trading Profile" description="Tell us about your trading experience." />;
const OnboardingRisk = () => <Placeholder title="Risk Preferences" description="Set your risk limits." />;
const OnboardingStrategy = () => <Placeholder title="Strategy Declaration" description="Describe your trading strategies." />;
const OnboardingBrokerConsent = () => <Placeholder title="Broker Connection" description="Connect your broker for trade sync." />;

export const router = createBrowserRouter([
  {
    // Root layout provides AuthContext to all routes
    element: <RootLayout />,
    children: [
      // Public pages
      {
        element: <PublicLayout />,
        children: [
          { path: '/', element: <Home /> },
          { path: '/how-it-works', element: <HowItWorks /> },
          { path: '/what-we-evaluate', element: <WhatWeEvaluate /> },
          { path: '/what-we-dont-do', element: <WhatWeDontDo /> },
          { path: '/pricing', element: <Pricing /> },
          { path: '/faq', element: <FAQ /> },
          { path: '/about', element: <About /> },
          { path: '/legal/disclaimer', element: <Disclaimer /> },
          { path: '/legal/terms', element: <Terms /> },
          { path: '/legal/privacy', element: <Privacy /> },
        ],
      },

      // Auth
      { path: '/auth/login', element: <Login /> },
      { path: '/auth/signup', element: <Login /> },
      { path: '/auth/forgot-password', element: <Placeholder title="Forgot Password" /> },

      // Onboarding
      {
        path: '/onboarding',
        element: <OnboardingLayout />,
        children: [
          { path: 'welcome', element: <OnboardingWelcome /> },
          { path: 'profile', element: <OnboardingProfile /> },
          { path: 'risk', element: <OnboardingRisk /> },
          { path: 'strategy', element: <OnboardingStrategy /> },
          { path: 'broker-consent', element: <OnboardingBrokerConsent /> },
        ],
      },

      // App portal (protected)
      {
        path: '/app',
        element: (
          <ProtectedRoute>
            <ChartProvider>
              <AppLayout />
            </ChartProvider>
          </ProtectedRoute>
        ),
        children: [
          { index: true, element: <Overview /> },
          { path: 'campaigns', element: <Campaigns /> },
          { path: 'campaigns/:campaignId', element: <CampaignDetail /> },
          { path: 'evaluate', element: <EvaluateIdea /> },
          { path: 'trades', element: <Trades /> },
          { path: 'trades/:tradeId', element: <TradeDetail /> },
          { path: 'transactions', element: <Transactions /> },
          { path: 'insights', element: <Insights /> },
          { path: 'journal', element: <Journal /> },
          { path: 'settings/profile', element: <SettingsProfile /> },
          { path: 'settings/risk', element: <SettingsRisk /> },
          { path: 'settings/strategies', element: <SettingsStrategies /> },
          { path: 'settings/brokers', element: <SettingsBrokers /> },
          { path: 'settings/evaluation-controls', element: <SettingsEvaluationControls /> },
          { path: 'settings/data-privacy', element: <SettingsDataPrivacy /> },
        ],
      },

      // Help
      {
        path: '/help',
        element: <PublicLayout />,
        children: [
          { index: true, element: <HelpIndex /> },
          { path: 'evaluations', element: <HelpEvaluations /> },
          { path: 'behavioral-signals', element: <HelpBehavioral /> },
          { path: 'why-flags', element: <HelpWhyFlags /> },
          { path: 'common-misunderstandings', element: <HelpMisunderstandings /> },
          { path: 'contact', element: <HelpContact /> },
        ],
      },
    ],
  },
]);
