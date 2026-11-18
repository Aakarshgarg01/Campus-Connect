import { useEffect, useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Info, RefreshCw, Save } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Meter, PageHeader, SectionTitle, Stat, StatusBadge } from "@/components/campus/core";
import { PredictionChart } from "@/components/campus/charts";
import { Loadable, PredictionResult, RiskBadge } from "@/components/campus/prediction";
import { useAuth } from "@/context/auth-context";
import { getApiErrorMessage } from "@/lib/api-error";
import { predictionApi } from "@/services/predictionApi";
import { studentApi } from "@/services/studentApi";
import {
  FEATURE_KEYS,
  STAGE_LABEL,
  type AcademicData,
  type Prediction,
  type PredictionInputs,
  type Simulation,
  type Stage,
} from "@/services/types";
import {
  classifyZone,
  formatDate,
  inputsFromRecords,
  markLabel,
  overallSubjectAverage,
  pct,
  percent,
  subjectAverage,
  zoneLabel,
} from "@/utils/academic";

// --- shared data -------------------------------------------------------------------------------

function useStudentData() {
  const me = useQuery({ queryKey: ["me"], queryFn: studentApi.me });
  const id = me.data?.id;
  const academic = useQuery({
    queryKey: ["academic", id],
    queryFn: () => studentApi.academic(id!),
    enabled: !!id,
  });
  const history = useQuery({
    queryKey: ["history", id],
    queryFn: () => studentApi.history(id!),
    enabled: !!id,
  });
  const target = useQuery({
    queryKey: ["target", id],
    queryFn: () => studentApi.target(id!),
    enabled: !!id,
  });
  const queries = [me, academic, history, target];
  return {
    me: me.data,
    academic: academic.data,
    history: history.data ?? [],
    target: target.data?.target_percentage ?? null,
    isLoading: queries.some((q) => q.isLoading),
    error: queries.find((q) => q.error)?.error ?? null,
    retry: () => queries.forEach((q) => void q.refetch()),
  };
}

/** Stage 2 once every subject has Internal 2, otherwise Stage 1. */
function availableStage(academic: AcademicData | undefined): Stage {
  const records = academic?.records ?? [];
  return records.length > 0 && records.every((r) => r.internal2) ? "stage2" : "stage1";
}

const chartData = (history: Prediction[]) =>
  [...history].reverse().map((p) => ({
    stage: `${STAGE_LABEL[p.stage]} · ${formatDate(p.created_at)}`,
    value: p.predicted_marks,
  }));

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}

function RefreshPrediction({
  studentId,
  academic,
}: {
  studentId: number;
  academic: AcademicData | undefined;
}) {
  const client = useQueryClient();
  const stage = availableStage(academic);
  const mutation = useMutation({
    mutationFn: () => predictionApi.predict(studentId, stage),
    onSuccess: () => {
      toast.success(`${STAGE_LABEL[stage]} prediction updated from your records`);
      void client.invalidateQueries({ queryKey: ["history", studentId] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  return (
    <Button variant="outline" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
      <RefreshCw className={mutation.isPending ? "animate-spin" : ""} />
      {mutation.isPending ? "Predicting…" : "Update prediction from my records"}
    </Button>
  );
}

// --- pages ---------------------------------------------------------------------------------------

export function StudentDashboard() {
  const { user } = useAuth();
  const data = useStudentData();
  const latest = data.history[0];
  const gap = latest && data.target !== null ? data.target - latest.predicted_marks : null;
  const records = data.academic?.records ?? [];
  const overall = overallSubjectAverage(records);
  const focus = records
    .map((r) => ({ r, avg: subjectAverage(r) }))
    .filter((x): x is { r: (typeof records)[number]; avg: number } => x.avg !== null)
    .sort((a, b) => a.avg - b.avg)
    .slice(0, 2);

  return (
    <>
      <PageHeader
        title={`${greeting()}, ${user?.name.split(" ")[0] ?? ""}`}
        description={data.me ? `Semester ${data.me.semester} · ${data.me.department}` : undefined}
        actions={data.me && <RefreshPrediction studentId={data.me.id} academic={data.academic} />}
      />
      <Loadable
        isLoading={data.isLoading}
        error={data.error}
        onRetry={data.retry}
        loadingTitle="Loading your workspace…"
      >
        <div className="stats-row">
          <Stat
            label="Predicted final performance"
            value={pct(latest?.predicted_marks, 1)}
            detail={
              latest
                ? `${STAGE_LABEL[latest.stage]} · ${formatDate(latest.created_at)}`
                : "No prediction yet"
            }
          />
          <Stat
            label="Personal target"
            value={pct(data.target)}
            detail={data.target === null ? "Not set" : "Set by you"}
          />
          <Stat
            label="Gap to target"
            value={gap === null ? "—" : gap > 0 ? `${gap.toFixed(1)} pp` : "On target"}
            detail={
              gap === null
                ? "Needs a prediction and a target"
                : gap > 0
                  ? "Below your target"
                  : "At or above target"
            }
            tone={gap !== null && gap > 0 ? "warning" : "default"}
          />
          <Stat
            label="Attendance"
            value={pct(data.academic?.attendance_percentage, 1)}
            detail={data.academic ? `Semester ${data.academic.semester}` : undefined}
          />
        </div>
        <section className="split-main">
          <div className="primary-panel">
            <SectionTitle
              title="Your current position"
              description="Latest prediction compared with your personal target."
              aside={latest && <RiskBadge risk={latest.risk_level} />}
            />
            {latest ? (
              <>
                <div className="position-number">
                  <strong>{latest.predicted_marks.toFixed(1)}%</strong>
                  <span>Predicted final performance</span>
                </div>
                <Meter value={Math.round(latest.predicted_marks)} target={data.target} />
                <div className="position-details">
                  <div>
                    <span>Target</span>
                    <b>{pct(data.target)}</b>
                  </div>
                  <div>
                    <span>Likely range</span>
                    <b>
                      {latest.interval
                        ? `${latest.interval.low.toFixed(0)}–${latest.interval.high.toFixed(0)}%`
                        : "—"}
                    </b>
                  </div>
                  <div>
                    <span>Prediction stage</span>
                    <b>{STAGE_LABEL[latest.stage]}</b>
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-panel">
                <strong>No prediction yet</strong>
                <p>
                  Once your faculty has entered your attendance and Internal 1 marks, you can
                  generate one from your records.
                </p>
              </div>
            )}
            <p className="prediction-note">
              <Info />
              This is an estimated final-exam performance, not a guaranteed result.
            </p>
          </div>
          <aside className="focus-panel">
            <SectionTitle
              title="Focus areas"
              description="Your lowest subjects by internal test average"
            />
            {focus.length === 0 && <p className="field-hint">No subject marks recorded yet.</p>}
            {focus.map(({ r, avg }, i) => {
              const zone = overall !== null ? classifyZone(avg, overall) : "yellow";
              return (
                <Link
                  to="/student/performance"
                  className={`focus-item ${zone === "red" ? "danger" : "warning"}`}
                  key={r.subject_name}
                >
                  <span>0{i + 1}</span>
                  <div>
                    <b>{r.subject_name}</b>
                    <small>
                      {avg.toFixed(1)}% · {zoneLabel(zone)}
                    </small>
                  </div>
                  <ArrowRight />
                </Link>
              );
            })}
          </aside>
        </section>
        {latest && <PredictionResult result={latest} title="Latest prediction explained" />}
        {data.history.length > 0 && (
          <section className="plain-section" style={{ marginTop: 24 }}>
            <SectionTitle
              title="Prediction history"
              description="How the expected final-exam performance changed during the semester."
            />
            <PredictionChart data={chartData(data.history)} target={data.target} />
          </section>
        )}
      </Loadable>
    </>
  );
}

export function PerformancePage() {
  const data = useStudentData();
  const records = data.academic?.records ?? [];
  const overall = overallSubjectAverage(records);
  const missingI2 = records.filter((r) => !r.internal2).map((r) => r.subject_name);
  return (
    <>
      <PageHeader
        title="Academic performance"
        description={
          data.academic
            ? `Raw marks and percentages for Semester ${data.academic.semester}.`
            : undefined
        }
      />
      <Loadable isLoading={data.isLoading} error={data.error} onRetry={data.retry}>
        <div className="summary-line">
          <div>
            <span>Internal test average</span>
            <strong>{pct(overall, 1)}</strong>
          </div>
          <div>
            <span>Subjects recorded</span>
            <strong>{records.length}</strong>
          </div>
          <div>
            <span>With Internal 2</span>
            <strong>
              {records.length - missingI2.length} of {records.length}
            </strong>
          </div>
          <div>
            <span>Attendance</span>
            <strong>{pct(data.academic?.attendance_percentage, 1)}</strong>
          </div>
        </div>
        <section className="plain-section">
          <SectionTitle
            title="Subject-wise performance"
            description="Maximum marks vary by assessment and subject."
          />
          {records.length === 0 ? (
            <p className="field-hint">No subject marks have been recorded for this semester yet.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Internal 1</th>
                    <th>Internal 2</th>
                    <th>Assignment</th>
                    <th className="numeric">Test average</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((r) => {
                    const avg = subjectAverage(r);
                    const zone =
                      avg !== null && overall !== null ? classifyZone(avg, overall) : null;
                    return (
                      <tr key={r.subject_name}>
                        <td>
                          <b>{r.subject_name}</b>
                        </td>
                        <td>
                          {markLabel(r.internal1)}
                          <small>{pct(percent(r.internal1))}</small>
                        </td>
                        <td>
                          {r.internal2 ? (
                            markLabel(r.internal2)
                          ) : (
                            <span className="pending-text">Not available yet</span>
                          )}
                          <small>{pct(percent(r.internal2))}</small>
                        </td>
                        <td>
                          {markLabel(r.assignment)}
                          <small>{pct(percent(r.assignment))}</small>
                        </td>
                        <td className="numeric">
                          <b>{pct(avg)}</b>
                        </td>
                        <td>{zone ? <StatusBadge status={zoneLabel(zone)} /> : "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {missingI2.length > 0 && records.length > 0 && (
            <div className="inline-notice">
              <Info />
              Internal 2 has not been recorded yet for {missingI2.join(", ")}. Their averages use
              Internal 1 only.
            </div>
          )}
        </section>
      </Loadable>
    </>
  );
}

export function PredictionsPage() {
  const data = useStudentData();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = data.history.find((p) => p.id === selectedId) ?? data.history[0];
  return (
    <>
      <PageHeader
        title="Prediction history"
        description="Expected final-exam performance at each assessment stage."
      />
      <Loadable isLoading={data.isLoading} error={data.error} onRetry={data.retry}>
        {data.history.length === 0 ? (
          <div className="empty-panel">
            <strong>No predictions yet</strong>
            <p>Predictions appear here once they are generated from your records.</p>
          </div>
        ) : (
          <>
            <section className="analysis-layout">
              <div className="plain-section chart-large">
                <SectionTitle
                  title="Predicted final performance"
                  description={
                    data.target !== null
                      ? `The dashed line is your target of ${data.target}%.`
                      : "Set a target to compare against."
                  }
                />
                <PredictionChart data={chartData(data.history)} target={data.target} />
              </div>
              <aside className="stage-list history-list">
                <SectionTitle
                  title="Stage record"
                  description="Select one to see its explanation."
                />
                {data.history.map((p, i) => (
                  <button key={p.id} onClick={() => setSelectedId(p.id)}>
                    <div className={`stage ${selected?.id === p.id ? "selected" : ""}`}>
                      <span>{data.history.length - i}</span>
                      <div>
                        <b>{STAGE_LABEL[p.stage]}</b>
                        <strong>{p.predicted_marks.toFixed(1)}%</strong>
                        <small>
                          {formatDate(p.created_at)} · {p.risk_level} risk
                        </small>
                      </div>
                    </div>
                  </button>
                ))}
              </aside>
            </section>
            {selected && <PredictionResult result={selected} />}
          </>
        )}
        <section className="input-contract">
          <h3>What each stage uses</h3>
          <div>
            <b>Stage 1</b>
            <span>Attendance, Internal 1 and assignment performance</span>
          </div>
          <div>
            <b>Stage 2</b>
            <span>Attendance, Internal 1, Internal 2 and assignment performance</span>
          </div>
        </section>
      </Loadable>
    </>
  );
}

export function ImprovementPage() {
  const data = useStudentData();
  const records = data.academic?.records ?? [];
  const overall = overallSubjectAverage(records);
  return (
    <>
      <PageHeader
        title="Improvement Zone"
        description="Rule-based subject comparison using your overall internal test average."
      />
      <Loadable isLoading={data.isLoading} error={data.error} onRetry={data.retry}>
        {overall === null ? (
          <div className="empty-panel">
            <strong>No subject marks yet</strong>
            <p>This page fills in once Internal 1 marks are recorded.</p>
          </div>
        ) : (
          <>
            <div className="improvement-summary">
              <div>
                <span>Your overall test average</span>
                <strong>{pct(overall, 1)}</strong>
                <small>Comparison band: ±10% relative</small>
              </div>
              <div className="zone-legend">
                <span>
                  <i className="red" />
                  Focus area
                </span>
                <span>
                  <i className="yellow" />
                  Continue effort
                </span>
                <span>
                  <i className="green" />
                  Performing well
                </span>
              </div>
            </div>
            <div className="zone-list">
              {records.map((r) => {
                const avg = subjectAverage(r);
                if (avg === null) return null;
                const zone = classifyZone(avg, overall);
                return (
                  <article key={r.subject_name} className={`zone-row zone-${zone}`}>
                    <div className="zone-indicator" />
                    <div>
                      <h3>{r.subject_name}</h3>
                      <p>
                        {r.internal2
                          ? "Internal 1 and Internal 2 average"
                          : "Temporary result based on Internal 1 only"}
                      </p>
                    </div>
                    <strong>{pct(avg)}</strong>
                    <StatusBadge status={zoneLabel(zone)} />
                  </article>
                );
              })}
            </div>
          </>
        )}
        <div className="method-note">
          <Info />
          <p>
            <b>How this is classified</b>
            <span>
              Subjects are compared with your overall average using a 10% relative band. This is
              rule-based analysis, not a prediction.
            </span>
          </p>
        </div>
      </Loadable>
    </>
  );
}

const SLIDERS: [keyof PredictionInputs, string][] = [
  ["attendance", "Overall attendance"],
  ["internal1", "Internal 1 performance"],
  ["internal2", "Internal 2 performance"],
  ["assignment", "Assignment performance"],
];

export function SimulatorPage() {
  const data = useStudentData();
  const latest = data.history[0];
  const [stage, setStage] = useState<Stage>("stage1");
  const [values, setValues] = useState<Required<PredictionInputs>>({
    attendance: 75,
    internal1: 75,
    internal2: 75,
    assignment: 75,
  });
  const [initialised, setInitialised] = useState(false);
  const [result, setResult] = useState<Simulation | null>(null);

  // Prefill from the latest prediction's inputs, else from stored records.
  useEffect(() => {
    if (initialised || data.isLoading) return;
    const fromRecords = data.academic
      ? inputsFromRecords(data.academic.records, data.academic.attendance_percentage)
      : {};
    const fromLatest = latest
      ? {
          attendance: latest.inputs[FEATURE_KEYS.attendance],
          internal1: latest.inputs[FEATURE_KEYS.internal1],
          internal2: latest.inputs[FEATURE_KEYS.internal2],
          assignment: latest.inputs[FEATURE_KEYS.assignment],
        }
      : {};
    setValues((v) => {
      const next = { ...v };
      for (const [key] of SLIDERS) {
        const value = fromLatest[key] ?? fromRecords[key];
        if (value !== undefined) next[key] = Math.round(value);
      }
      return next;
    });
    setStage(latest?.stage ?? availableStage(data.academic));
    setInitialised(true);
  }, [initialised, data.isLoading, data.academic, latest]);

  const mutation = useMutation({
    mutationFn: () => {
      const { internal2, ...rest } = values;
      return predictionApi.simulate(stage, stage === "stage2" ? { ...rest, internal2 } : rest);
    },
    onSuccess: setResult,
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const delta = result && latest ? result.predicted_marks - latest.predicted_marks : null;

  return (
    <>
      <PageHeader
        title="What-if Simulator"
        description="Explore how changes in your academic inputs could affect your predicted performance. Nothing is saved."
      />
      <Loadable isLoading={data.isLoading} error={data.error} onRetry={data.retry}>
        <section className="simulator-grid">
          <div className="sim-inputs">
            <SectionTitle
              title="Adjust academic inputs"
              description="Percentages are prefilled from your latest prediction or records."
            />
            <div className="toggle-row" role="group" aria-label="Stage">
              {(["stage1", "stage2"] as Stage[]).map((s) => (
                <button
                  key={s}
                  className={stage === s ? "selected" : ""}
                  onClick={() => {
                    setStage(s);
                    setResult(null);
                  }}
                >
                  {s === "stage1" ? "Stage 1 (before Internal 2)" : "Stage 2 (with Internal 2)"}
                </button>
              ))}
            </div>
            {SLIDERS.filter(([key]) => stage === "stage2" || key !== "internal2").map(
              ([key, label]) => (
                <label key={key}>
                  <span>
                    {label}
                    <b>{values[key]}%</b>
                  </span>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={values[key]}
                    onChange={(e) => setValues((v) => ({ ...v, [key]: Number(e.target.value) }))}
                  />
                </label>
              ),
            )}
            <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
              {mutation.isPending ? "Running simulation…" : "Run simulation"}
            </Button>
          </div>
          <div className="sim-results">
            <SectionTitle title="Prediction comparison" />
            <div>
              <span>Latest saved prediction</span>
              <strong>{pct(latest?.predicted_marks, 1)}</strong>
            </div>
            <ArrowRight />
            <div>
              <span>Simulated prediction</span>
              <strong>{pct(result?.predicted_marks, 1)}</strong>
            </div>
            {delta !== null && (
              <p className={delta >= 0 ? "positive" : "negative"}>
                {delta >= 0 ? "+" : ""}
                {delta.toFixed(1)} percentage points
              </p>
            )}
            <div className="warning-note">
              <Info />
              Simulation only — an estimate, not a guaranteed result.
            </div>
          </div>
        </section>
        {result && <PredictionResult result={result} />}
      </Loadable>
    </>
  );
}

export function TargetPage() {
  const data = useStudentData();
  const client = useQueryClient();
  const [value, setValue] = useState<number | null>(null);
  const current = value ?? data.target ?? 75;
  const latest = data.history[0];
  const mutation = useMutation({
    mutationFn: () => studentApi.saveTarget(data.me!.id, current),
    onSuccess: () => {
      toast.success("Target saved");
      void client.invalidateQueries({ queryKey: ["target", data.me?.id] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const valid = Number.isFinite(current) && current >= 1 && current <= 100;
  return (
    <>
      <PageHeader
        title="My target"
        description="Set the final performance percentage you want to work toward."
      />
      <Loadable isLoading={data.isLoading} error={data.error} onRetry={data.retry}>
        <section className="target-layout">
          <div className="target-form">
            <SectionTitle
              title="Target final performance"
              description="This target is a percentage, not a CGPA conversion."
            />
            <label>
              Target percentage
              <div className="suffix-input">
                <Input
                  type="number"
                  min="1"
                  max="100"
                  value={current}
                  onChange={(e) => setValue(Number(e.target.value))}
                />
                <span>%</span>
              </div>
            </label>
            <Button
              onClick={() => mutation.mutate()}
              disabled={!valid || mutation.isPending || !data.me}
            >
              <Save />
              {mutation.isPending ? "Saving…" : "Save target"}
            </Button>
            {!valid && <p className="text-sm text-destructive">Enter a value between 1 and 100.</p>}
            {mutation.isSuccess && (
              <p className="saved">
                <CheckCircle2 />
                Target saved.
              </p>
            )}
          </div>
          <div className="target-comparison">
            <div>
              <span>Current prediction</span>
              <strong>{pct(latest?.predicted_marks, 1)}</strong>
            </div>
            <div>
              <span>Your target</span>
              <strong>{pct(current)}</strong>
            </div>
            <div>
              <span>Gap</span>
              <strong>
                {latest ? `${Math.max(0, current - latest.predicted_marks).toFixed(1)} pp` : "—"}
              </strong>
            </div>
            {latest && <Meter value={Math.round(latest.predicted_marks)} target={current} />}
          </div>
        </section>
      </Loadable>
    </>
  );
}

export function StudentProfilePage() {
  const { user } = useAuth();
  const data = useStudentData();
  const initials = useMemo(
    () =>
      user?.name
        .split(" ")
        .map((x) => x[0])
        .slice(0, 2)
        .join("") ?? "",
    [user],
  );
  return (
    <>
      <PageHeader title="Profile" description="Your account and academic details." />
      <Loadable isLoading={data.isLoading} error={data.error} onRetry={data.retry}>
        <section className="profile-sheet">
          <div className="profile-heading">
            <div className="profile-avatar">{initials}</div>
            <div>
              <h2>{user?.name}</h2>
              <span>Student · Semester {data.me?.semester}</span>
            </div>
          </div>
          <dl>
            <div>
              <dt>Roll number</dt>
              <dd>{data.me?.roll_number}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{user?.email}</dd>
            </div>
            <div>
              <dt>Department</dt>
              <dd>{data.me?.department}</dd>
            </div>
            <div>
              <dt>Semester</dt>
              <dd>{data.me?.semester}</dd>
            </div>
          </dl>
        </section>
      </Loadable>
    </>
  );
}
