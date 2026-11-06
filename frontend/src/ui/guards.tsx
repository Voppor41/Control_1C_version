import { Navigate, Outlet } from "react-router-dom";
import type { RoleCode } from "../api/types";
import { useAuth } from "../auth/session";
import { BootScreen, Shell } from "./shell";
import { EmptyState } from "./ui";
import { Link } from "react-router-dom";

export function RequireAuth() {
  const { status } = useAuth();
  if (status === "loading") return <BootScreen />;
  if (status === "anon") return <Navigate to="/login" replace />;
  return (
    <Shell>
      <Outlet />
    </Shell>
  );
}

export function RequireRole({ roles }: { roles: RoleCode[] }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) {
    return (
      <EmptyState
        title="Этот раздел для другой роли"
        text="Откройте обзор — там собрано то, что доступно вашей учётной записи."
        action={
          <Link className="btn btn-primary" to="/">
            На обзор
          </Link>
        }
      />
    );
  }
  return <Outlet />;
}

export function LoginGate({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  if (status === "loading") return <BootScreen />;
  if (status === "ready") return <Navigate to="/" replace />;
  return children;
}
