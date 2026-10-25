import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { CommandCenterLayout } from "./layouts/CommandCenterLayout";
import { OverviewPage } from "./pages/OverviewPage";
import { GlobalMapPage } from "./pages/GlobalMapPage";
import { TransactionMonitorPage } from "./pages/TransactionMonitorPage";
import { FlaggedAccountsPage } from "./pages/FlaggedAccountsPage";
import { NetworkIntelligencePage } from "./pages/NetworkIntelligencePage";
import { InvestigationWorkspacePage } from "./pages/InvestigationWorkspacePage";
import { ExplainableAIPage } from "./pages/ExplainableAIPage";
import { RiskAnalyticsPage } from "./pages/RiskAnalyticsPage";
import { WhatIfLabPage } from "./pages/WhatIfLabPage";
import { FinancialContextPage } from "./pages/FinancialContextPage";
import { AuditTrailPage } from "./pages/AuditTrailPage";
import { SettingsModelOpsPage } from "./pages/SettingsModelOpsPage";

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <CommandCenterLayout>
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/map" element={<GlobalMapPage />} />
          <Route path="/transactions" element={<TransactionMonitorPage />} />
          <Route path="/flagged-accounts" element={<FlaggedAccountsPage />} />
          <Route path="/network" element={<NetworkIntelligencePage />} />
          <Route path="/investigations" element={<InvestigationWorkspacePage />} />
          <Route path="/explainable-ai" element={<ExplainableAIPage />} />
          <Route path="/risk-analytics" element={<RiskAnalyticsPage />} />
          <Route path="/what-if" element={<WhatIfLabPage />} />
          <Route path="/context" element={<FinancialContextPage />} />
          <Route path="/audit-trail" element={<AuditTrailPage />} />
          <Route path="/settings" element={<SettingsModelOpsPage />} />
        </Routes>
      </CommandCenterLayout>
    </BrowserRouter>
  );
};

export default App;

