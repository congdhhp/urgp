import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { useAuth } from "./contexts/AuthContext";
import { ActivityPage } from "./pages/ActivityPage";
import { BuildDetailPage } from "./pages/BuildDetailPage";
import { ComparisonPage } from "./pages/ComparisonPage";
import { LoginPage } from "./pages/LoginPage";
import { PackageDetailPage } from "./pages/PackageDetailPage";
import { ProductReleasesPage } from "./pages/ProductReleasesPage";
import { ProductsPage } from "./pages/ProductsPage";
import { ReleaseBuildsPage } from "./pages/ReleaseBuildsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SearchPage } from "./pages/SearchPage";
import { SettingsPage } from "./pages/SettingsPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedShell />}>
        <Route index element={<Navigate to="/products" replace />} />
        <Route path="/products" element={<ProductsPage />} />
        <Route path="/products/:productId" element={<ProductReleasesPage />} />
        <Route path="/products/:productId/releases/:releaseId" element={<ReleaseBuildsPage />} />
        <Route path="/builds/:productId/:buildId" element={<BuildDetailPage />} />
        <Route path="/packages/:productId/:buildId/:artifactId" element={<PackageDetailPage />} />
        <Route path="/compare" element={<ComparisonPage />} />
        <Route path="/activity" element={<ActivityPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/search" element={<SearchPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/products" replace />} />
    </Routes>
  );
}

function ProtectedShell() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <AppShell />;
}
