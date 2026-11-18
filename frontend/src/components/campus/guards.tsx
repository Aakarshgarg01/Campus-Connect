import { useEffect, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { useAuth } from "@/context/auth-context";
import { workspaceOf } from "@/services/authApi";
import type { Workspace } from "@/services/types";
import { DataState } from "./core";

export function RoleGuard({ role, children }: { role: Workspace; children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const workspace = user ? workspaceOf(user) : null;
  const userWorkspace = workspace === "student" ? "/student/dashboard" : "/faculty/dashboard";

  useEffect(() => {
    if (isLoading) return;
    if (!user) {
      navigate({ to: "/login", replace: true });
      return;
    }
    if (workspace !== role) {
      toast.error("This workspace is not available for your account.");
      navigate({ to: userWorkspace, replace: true });
    }
  }, [isLoading, user, role, workspace, userWorkspace, navigate]);

  if (isLoading || !user || workspace !== role) {
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
