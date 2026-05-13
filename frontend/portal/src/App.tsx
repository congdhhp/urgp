import { lazy, Suspense } from "react";
import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { useAuth } from "./contexts/AuthContext";
import { LoginPage } from "./pages/LoginPage";

const ActivityPage = lazy(() => import("./pages/ActivityPage").then((module) => ({ default: module.ActivityPage })));
const BuildDetailPage = lazy(() => import("./pages/BuildDetailPage").then((module) => ({ default: module.BuildDetailPage })));
const ComparisonPage = lazy(() => import("./pages/ComparisonPage").then((module) => ({ default: module.ComparisonPage })));
const PackageDetailPage = lazy(() => import("./pages/PackageDetailPage").then((module) => ({ default: module.PackageDetailPage })));
const ProductReleasesPage = lazy(() => import("./pages/ProductReleasesPage").then((module) => ({ default: module.ProductReleasesPage })));
const ProductsPage = lazy(() => import("./pages/ProductsPage").then((module) => ({ default: module.ProductsPage })));
const ReleaseBuildsPage = lazy(() => import("./pages/ReleaseBuildsPage").then((module) => ({ default: module.ReleaseBuildsPage })));
const ReportsPage = lazy(() => import("./pages/ReportsPage").then((module) => ({ default: module.ReportsPage })));
const SearchPage = lazy(() => import("./pages/SearchPage").then((module) => ({ default: module.SearchPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedShell />}>
        <Route index element={<Navigate to="/products" replace />} />
        <Route path="/products" element={<LazyRoute><ProductsPage /></LazyRoute>} />
        <Route path="/products/:productId" element={<LazyRoute><ProductReleasesPage /></LazyRoute>} />
        <Route path="/products/:productId/releases/:releaseId" element={<LazyRoute><ReleaseBuildsPage /></LazyRoute>} />
        <Route path="/builds/:productId/:buildId" element={<LazyRoute><BuildDetailPage /></LazyRoute>} />
        <Route path="/packages/:productId/:buildId/:artifactId" element={<LazyRoute><PackageDetailPage /></LazyRoute>} />
        <Route path="/compare" element={<LazyRoute><ComparisonPage /></LazyRoute>} />
        <Route path="/activity" element={<LazyRoute><ActivityPage /></LazyRoute>} />
        <Route path="/reports" element={<LazyRoute><ReportsPage /></LazyRoute>} />
        <Route path="/settings" element={<LazyRoute><SettingsPage /></LazyRoute>} />
        <Route path="/search" element={<LazyRoute><SearchPage /></LazyRoute>} />
      </Route>
      <Route path="*" element={<Navigate to="/products" replace />} />
    </Routes>
  );
}

function LazyRoute({ children }: { children: ReactNode }) {
  return <Suspense fallback={<div className="route-loading" role="status" aria-label="Loading view" />}>{children}</Suspense>;
}

function ProtectedShell() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <AppShell />;
}
