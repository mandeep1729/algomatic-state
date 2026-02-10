import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./AppShell";
import { OverviewPage } from "../pages/OverviewPage";
import { CampaignsListPage } from "../pages/CampaignsListPage";
import { CampaignDetailPage } from "../pages/CampaignDetailPage";
import { EvaluateIdeaPage } from "../pages/EvaluateIdeaPage";
import { BrokersSettingsPage } from "../pages/BrokersSettingsPage";
import { NotFoundPage } from "../pages/NotFoundPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/app/overview" replace />} />
      <Route path="/app" element={<AppShell />}>
        <Route path="overview" element={<OverviewPage />} />
        <Route path="trades" element={<CampaignsListPage />} />
        <Route path="trade/:campaignId" element={<CampaignDetailPage />} />
        <Route path="evaluate" element={<EvaluateIdeaPage />} />
        <Route path="settings/brokers" element={<BrokersSettingsPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
