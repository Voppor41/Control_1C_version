import { Navigate, Route, Routes } from "react-router-dom";
import { ChecksPage } from "./pages/ChecksPage";
import { ClientPage } from "./pages/ClientPage";
import { ClientsPage } from "./pages/ClientsPage";
import { ConfigurationPage } from "./pages/ConfigurationPage";
import { ConfigurationsPage } from "./pages/ConfigurationsPage";
import { HomePage } from "./pages/HomePage";
import { InstallationsPage } from "./pages/InstallationsPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/misc";
import { NotificationsPage } from "./pages/NotificationsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SlotsPage } from "./pages/SlotsPage";
import { UpdatePage } from "./pages/UpdatePage";
import { UpdatesPage } from "./pages/UpdatesPage";
import { UsersPage } from "./pages/UsersPage";
import { LoginGate, RequireAuth, RequireRole } from "./ui/guards";

export function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <LoginGate>
            <LoginPage />
          </LoginGate>
        }
      />
      <Route element={<RequireAuth />}>
        <Route index element={<HomePage />} />
        <Route path="clients" element={<ClientsPage />} />
        <Route path="clients/:clientId" element={<ClientPage />} />
        <Route path="configurations" element={<ConfigurationsPage />} />
        <Route path="configurations/:configurationId" element={<ConfigurationPage />} />
        <Route path="installations" element={<InstallationsPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="updates" element={<UpdatesPage />} />
        <Route path="updates/:updateId" element={<UpdatePage />} />
        <Route element={<RequireRole roles={["admin", "specialist", "manager"]} />}>
          <Route path="checks" element={<ChecksPage />} />
          <Route path="slots" element={<SlotsPage />} />
        </Route>
        <Route element={<RequireRole roles={["admin", "manager"]} />}>
          <Route path="reports" element={<ReportsPage />} />
        </Route>
        <Route element={<RequireRole roles={["admin"]} />}>
          <Route path="users" element={<UsersPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
