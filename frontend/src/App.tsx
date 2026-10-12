import { Navigate, Route, Routes } from "react-router-dom";
import { ProfileBanner } from "./components/ProfileBanner";
import { Shell } from "./components/Shell";
import { AssetDetailPage } from "./pages/AssetDetailPage";
import { AssetsPage } from "./pages/AssetsPage";
import { AuditPage } from "./pages/AuditPage";
import { EmailPage } from "./pages/EmailPage";
import { DashboardPage } from "./pages/DashboardPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { IntelPage } from "./pages/IntelPage";
import { LockoutPage } from "./pages/LockoutPage";
import { MapPage } from "./pages/MapPage";
import { LoginPage } from "./pages/LoginPage";
import { PasswordPolicyPage } from "./pages/PasswordPolicyPage";
import { RolesPage } from "./pages/RolesPage";
import { SessionsPage } from "./pages/SessionsPage";
import { UsersPage } from "./pages/UsersPage";
import { useSession } from "./state/session";
import { useTranslation } from "react-i18next";

function RequireSession() {
  const { session, loading } = useSession();
  const { t } = useTranslation();
  if (loading) return <p style={{ padding: 24 }}>{t("common.loading")}</p>;
  if (!session?.authenticated) return <Navigate to="/login" replace />;
  return <Shell />;
}

export function App() {
  return (
    <>
      <ProfileBanner position="top" />
      <AppRoutes />
      <ProfileBanner position="bottom" />
    </>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireSession />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/settings/password" element={<PasswordPolicyPage />} />
        <Route path="/settings/lockout" element={<LockoutPage />} />
        <Route path="/settings/sessions" element={<SessionsPage />} />
        <Route path="/settings/email" element={<EmailPage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/intel" element={<IntelPage />} />
        <Route path="/assets" element={<AssetsPage />} />
        <Route path="/assets/:id" element={<AssetDetailPage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/roles" element={<RolesPage />} />
        <Route path="/audit" element={<AuditPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
