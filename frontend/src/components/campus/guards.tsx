import { useEffect, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { useAuth } from "@/context/auth-context";
import type { Role } from "@/data/mock-data";
import { DataState } from "./core";

export function RoleGuard({ role, children }: { role: Role; children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const userWorkspace = user?.role === "student" ? "/student/dashboard" : "/faculty/dashboard";

  useEffect(() => {
    if (isLoading) return;
    if (!user) {
      navigate({ to: "/login", replace: true });
      return;
    }
    if (user.role !== role) {
      toast.error("This workspace is not available for your account.");
      navigate({ to: userWorkspace, replace: true });
    }
  }, [isLoading, user, role, userWorkspace, navigate]);

  if (isLoading || !user || user.role !== role) {
    return (
      <div className="center-state">
        <DataState
          type="loading"
          title={isLoading ? "Preparing your workspace…" : "Redirecting…"}
        />
      </div>
    );
  }

  return <>{children}</>;
}
