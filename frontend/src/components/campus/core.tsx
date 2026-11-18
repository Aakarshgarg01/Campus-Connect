import type { ReactNode } from "react";
import { AlertCircle, Inbox, LoaderCircle } from "lucide-react";
import { cn } from "@/lib/utils";
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string | undefined;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}
export function SectionTitle({
  title,
  description,
  aside,
}: {
  title: string;
  description?: string | undefined;
  aside?: ReactNode;
}) {
  return (
    <div className="section-title">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {aside}
    </div>
  );
}
export function StatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  const tone =
    s.includes("below") || s.includes("significant")
      ? "danger"
      : s.includes("track") || s.includes("performing") || s.includes("improved")
        ? "success"
        : s.includes("pending") || s.includes("continued") || s.includes("monitoring")
          ? "warning"
          : "neutral";
  return <span className={cn("status-badge", `status-${tone}`)}>{status}</span>;
}
export function Stat({
  label,
  value,
  detail,
  tone = "default",
}: {
  label: string;
  value: string;
  detail?: string | undefined;
  tone?: string;
}) {
  return (
    <div className={cn("stat", tone !== "default" && `stat-${tone}`)}>
      <p>{label}</p>
      <strong>{value}</strong>
      {detail && <span>{detail}</span>}
    </div>
  );
}
export function DataState({
  type,
  title,
  detail,
}: {
  type: "loading" | "empty" | "error";
  title?: string | undefined;
  detail?: string | undefined;
}) {
  const Icon = type === "loading" ? LoaderCircle : type === "empty" ? Inbox : AlertCircle;
  return (
    <div className="data-state">
      <Icon className={type === "loading" ? "animate-spin" : ""} />
      <strong>
        {title ??
          (type === "loading"
            ? "Loading records…"
            : type === "empty"
              ? "No records available"
              : "Unable to load data")}
      </strong>
      {detail && <span>{detail}</span>}
    </div>
  );
}
export function Meter({
  value,
  target,
  label = "Predicted",
  targetLabel = "Target",
}: {
  value: number;
  target?: number | null;
  label?: string;
  targetLabel?: string;
}) {
  return (
    <div className="meter-wrap">
      <div className="meter-labels">
        <span>0%</span>
        <span>
          {label} {value}%
        </span>
        <span>100%</span>
      </div>
      <div className="meter">
        <div className="meter-fill" style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
        {target != null && (
          <span className="meter-target" style={{ left: `${target}%` }}>
            <i />
            {targetLabel} {target}%
          </span>
        )}
      </div>
    </div>
  );
}
export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand">
      <span className="brand-mark" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      {!compact && (
        <span>
          <b>Campus</b>Connect
        </span>
      )}
    </div>
  );
}
