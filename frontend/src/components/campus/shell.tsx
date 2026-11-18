import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import {
  BookOpen,
  ChartNoAxesCombined,
  ChevronRight,
  ClipboardCheck,
  FileSpreadsheet,
  Gauge,
  History,
  LogOut,
  Menu,
  MonitorCheck,
  SlidersHorizontal,
  Target,
  Upload,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Logo } from "./core";
import { useAuth } from "@/context/auth-context";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import type { Workspace } from "@/services/types";
const studentNav = [
  ["/student/dashboard", "Overview", Gauge],
  ["/student/performance", "Performance", BookOpen],
  ["/student/predictions", "Prediction History", History],
  ["/student/improvement-zone", "Improvement Zone", ChartNoAxesCombined],
  ["/student/simulator", "What-if Simulator", SlidersHorizontal],
  ["/student/target", "My Target", Target],
  ["/student/profile", "Profile", UserRound],
] as const;
const facultyNav = [
  ["/faculty/dashboard", "Overview", Gauge],
  ["/faculty/students", "Students", Users],
  ["/faculty/academic-data", "Academic Data", FileSpreadsheet],
  ["/faculty/upload", "Upload Data", Upload],
  ["/faculty/benchmark", "Benchmark", Target],
  ["/faculty/monitoring", "Monitoring", MonitorCheck],
  ["/faculty/profile", "Profile", UserRound],
] as const;
export function AppShell({ role, children }: { role: Workspace; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const loc = useLocation();
  const nav = useNavigate();
  const { user, logout } = useAuth();
  const items = role === "student" ? studentNav : facultyNav;
  const current = items.find(([p]) => loc.pathname === p || loc.pathname.startsWith(`${p}/`));

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logout();
      nav({ to: "/login", replace: true });
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <div className="app-shell">
      <button
        className={open ? "sidebar-backdrop open" : "sidebar-backdrop"}
        onClick={() => setOpen(false)}
        aria-label="Close navigation"
      />
      <aside className={open ? "sidebar open" : "sidebar"}>
        <div className="sidebar-brand">
          <Logo />
          <Button
            variant="ghost"
            size="icon"
            className="sidebar-close"
            onClick={() => setOpen(false)}
          >
            <X />
            <span className="sr-only">Close</span>
          </Button>
        </div>
        <div className="role-label">{role} workspace</div>
        <nav aria-label={`${role} navigation`}>
          {items.map(([path, label, Icon]) => (
            <Link
              key={path}
              to={path}
              onClick={() => setOpen(false)}
              activeProps={{ className: "active" }}
            >
              <Icon />
              <span>{label}</span>
              {loc.pathname === path && <ChevronRight className="nav-arrow" />}
            </Link>
          ))}
        </nav>
        <div className="sidebar-account">
          <div className="avatar">
            {user?.name
              ?.split(" ")
              .map((x) => x[0])
              .slice(0, 2)
              .join("")}
          </div>
          <div>
            <strong>{user?.name}</strong>
            <span>
              {user?.role === "student"
                ? (user.roll_number ?? "Student")
                : user?.role === "admin"
                  ? "Administrator"
                  : "Faculty"}
            </span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            title={loggingOut ? "Signing out…" : "Sign out"}
            aria-label="Sign out"
            disabled={loggingOut}
            onClick={handleLogout}
          >
            <LogOut />
          </Button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <Button variant="ghost" size="icon" className="menu-button" onClick={() => setOpen(true)}>
            <Menu />
            <span className="sr-only">Open navigation</span>
          </Button>
          <div>
            <span>CampusConnect</span>
            <strong>{current?.[1] ?? "Workspace"}</strong>
          </div>
          <div className="topbar-right">
            <div className="top-avatar">{user?.name?.charAt(0)}</div>
          </div>
        </header>
        <main>{children}</main>
      </div>
    </div>
  );
}
