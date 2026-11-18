import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  FileSpreadsheet,
  Filter,
  Info,
  Pencil,
  Plus,
  Save,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Meter, PageHeader, SectionTitle, Stat, StatusBadge } from "@/components/campus/core";
import { DistributionChart, ImportanceChart, PredictionChart } from "@/components/campus/charts";
import {
  Loadable,
  PredictionResult,
  RiskBadge,
  StatusFromRisk,
} from "@/components/campus/prediction";
import { useAuth } from "@/context/auth-context";
import { getApiErrorMessage } from "@/lib/api-error";
import { facultyApi } from "@/services/facultyApi";
import { predictionApi } from "@/services/predictionApi";
import { studentApi } from "@/services/studentApi";
import {
  MONITORING_STATUSES,
  STAGE_LABEL,
  type Mark,
  type MonitoringStatus,
  type OverviewStudent,
  type Prediction,
  type PredictionInputs,
  type RiskLevel,
  type Stage,
  type StudentInput,
  type SubjectRecord,
} from "@/services/types";
import { formatDate, inputsFromRecords, markLabel, pct, subjectAverage } from "@/utils/academic";

const SEMESTERS = Array.from({ length: 12 }, (_, i) => i + 1);
const RISK_ORDER: Record<RiskLevel, number> = { high: 0, medium: 1, low: 2 };

function useOverview(department?: string, semester?: number) {
  return useQuery({
    queryKey: ["overview", department ?? null, semester ?? null],
    queryFn: () =>
      facultyApi.overview({
        ...(department ? { department } : {}),
        ...(semester ? { semester } : {}),
      }),
  });
}

function useFilters() {
  const { user } = useAuth();
  const [department, setDepartment] = useState<string>(user?.department ?? "");
  const [semester, setSemester] = useState<number | undefined>(undefined);
  return { department, setDepartment, semester, setSemester };
}

function CohortFilters({
  departments,
  department,
  setDepartment,
  semester,
  setSemester,
}: ReturnType<typeof useFilters> & { departments: string[] }) {
  const options = Array.from(new Set([...departments, ...(department ? [department] : [])])).sort();
  return (
    <div className="table-tools">
      <label>
        Department
        <select value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">All departments</option>
          {options.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </label>
      <label>
        Semester
        <select
          value={semester ?? ""}
          onChange={(e) => setSemester(e.target.value ? Number(e.target.value) : undefined)}
        >
          <option value="">All semesters</option>
          {SEMESTERS.map((s) => (
            <option key={s} value={s}>
              Semester {s}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

function needsAttention(s: OverviewStudent, benchmark: number | null) {
  const p = s.latest_prediction;
  if (!p) return false;
  return p.risk_level !== "low" || (benchmark !== null && p.predicted_marks < benchmark);
}

function StudentsTable({
  items,
  benchmark,
  compact = false,
}: {
  items: OverviewStudent[];
  benchmark: number | null;
  compact?: boolean;
}) {
  if (items.length === 0)
    return (
      <p className="field-hint" style={{ padding: "12px 0" }}>
        No students to show.
      </p>
    );
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Student</th>
            <th>Roll number</th>
            {!compact && (
              <>
                <th className="numeric">Attendance</th>
                <th>Latest stage</th>
              </>
            )}
            <th className="numeric">Prediction</th>
            {benchmark !== null && <th className="numeric">Benchmark</th>}
            <th>Risk</th>
            {!compact && <th>Monitoring</th>}
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.id}>
              <td>
                <b>{s.name}</b>
                <small>
                  {s.department} · Sem {s.semester}
                </small>
              </td>
              <td className="mono">{s.roll_number}</td>
              {!compact && (
                <>
                  <td className="numeric">{pct(s.attendance_percentage, 1)}</td>
                  <td>{s.latest_prediction ? STAGE_LABEL[s.latest_prediction.stage] : "—"}</td>
                </>
              )}
              <td className="numeric">
                <b>{pct(s.latest_prediction?.predicted_marks, 1)}</b>
              </td>
              {benchmark !== null && <td className="numeric">{pct(benchmark)}</td>}
              <td>
                <StatusFromRisk risk={s.latest_prediction?.risk_level} />
              </td>
              {!compact && (
                <td>{s.monitoring_status ? <StatusBadge status={s.monitoring_status} /> : "—"}</td>
              )}
              <td>
                <Button variant="outline" size="sm" asChild>
                  <Link to="/faculty/students/$id" params={{ id: String(s.id) }}>
                    View
                  </Link>
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- dashboard -----------------------------------------------------------------------------------

export function FacultyDashboard() {
  const filters = useFilters();
  const overview = useOverview(filters.department || undefined, filters.semester);
  const allDepartments = useOverview();
  const importance = useQuery({
    queryKey: ["importance"],
    queryFn: predictionApi.featureImportance,
  });
  const [importanceStage, setImportanceStage] = useState<Stage>("stage2");
  const data = overview.data;
  const departments = useMemo(
    () => Array.from(new Set((allDepartments.data?.students ?? []).map((s) => s.department))),
    [allDepartments.data],
  );
  const attention = (data?.students ?? [])
    .filter((s) => needsAttention(s, data?.benchmark_percentage ?? null))
    .sort(
      (a, b) =>
        (a.latest_prediction?.predicted_marks ?? 0) - (b.latest_prediction?.predicted_marks ?? 0),
    );
  const stageImportance = importance.data?.stages.find((s) => s.stage === importanceStage);

  return (
    <>
      <PageHeader
        title="Cohort overview"
        description="Latest saved prediction for each student."
        actions={
          <Button variant="outline" asChild>
            <Link to="/faculty/students">
              <Plus />
              Add or find a student
            </Link>
          </Button>
        }
      />
      <CohortFilters {...filters} departments={departments} />
      <div style={{ height: 16 }} />
      <Loadable
        isLoading={overview.isLoading}
        error={overview.error}
        onRetry={() => void overview.refetch()}
      >
        {data && (
          <>
            <div className="stats-row">
              <Stat
                label="Students"
                value={String(data.total_students)}
                detail={`${data.with_prediction} with a prediction`}
              />
              <Stat
                label="High risk"
                value={String(data.risk_counts.high)}
                detail="Predicted below 50%"
                tone={data.risk_counts.high ? "danger" : "default"}
              />
              <Stat
                label="Below benchmark"
                value={data.below_benchmark === null ? "—" : String(data.below_benchmark)}
                detail={
                  data.benchmark_percentage === null
                    ? "Pick a department and semester with a benchmark"
                    : `Benchmark ${data.benchmark_percentage}%`
                }
                tone={data.below_benchmark ? "warning" : "default"}
              />
              <Stat
                label="Average prediction"
                value={pct(data.average_prediction, 1)}
                detail="Across students with a prediction"
              />
            </div>
            <section className="faculty-overview">
              <div className="plain-section">
                <SectionTitle
                  title="Prediction distribution"
                  description="Students grouped by latest predicted final-exam performance."
                />
                {data.with_prediction ? (
                  <DistributionChart data={data.distribution} />
                ) : (
                  <p className="field-hint">No predictions yet.</p>
                )}
              </div>
              <div className="workflow-panel">
                <SectionTitle
                  title="Risk breakdown"
                  description="Thresholds: high < 50%, medium 50–60%."
                />
                <ol>
                  {(["high", "medium", "low"] as RiskLevel[]).map((r) => (
                    <li key={r} className={r === "low" ? "done" : r === "medium" ? "current" : ""}>
                      <span>{data.risk_counts[r]}</span>
                      <div>
                        <b>
                          <RiskBadge risk={r} />
                        </b>
                        <small>
                          {data.risk_counts[r]} of {data.with_prediction} predicted students
                        </small>
                      </div>
                    </li>
                  ))}
                  <li>
                    <span>{data.total_students - data.with_prediction}</span>
                    <div>
                      <b>No prediction yet</b>
                      <small>Needs marks and attendance first</small>
                    </div>
                  </li>
                </ol>
              </div>
            </section>
            <section className="plain-section" style={{ marginBottom: 24 }}>
              <SectionTitle
                title="Students requiring attention"
                description="Medium or high risk, or below the benchmark."
                aside={
                  <Button variant="ghost" size="sm" asChild>
                    <Link to="/faculty/students">
                      View all students
                      <ChevronRight />
                    </Link>
                  </Button>
                }
              />
              <StudentsTable items={attention} benchmark={data.benchmark_percentage} compact />
            </section>
          </>
        )}
      </Loadable>
      <section className="plain-section">
        <SectionTitle
          title="What drives the predictions"
          description={
            stageImportance
              ? `Mean |SHAP| over the ${stageImportance.computed_on}. Associations, not causes.`
              : undefined
          }
          aside={
            <div className="toggle-row">
              {(["stage1", "stage2"] as Stage[]).map((s) => (
                <button
                  key={s}
                  className={importanceStage === s ? "selected" : ""}
                  onClick={() => setImportanceStage(s)}
                >
                  {s === "stage1" ? "Stage 1" : "Stage 2"}
                </button>
              ))}
            </div>
          }
        />
        <Loadable
          isLoading={importance.isLoading}
          error={importance.error}
          onRetry={() => void importance.refetch()}
        >
          {stageImportance && <ImportanceChart values={stageImportance.values} />}
        </Loadable>
      </section>
    </>
  );
}

// --- students list -------------------------------------------------------------------------------

const EMPTY_STUDENT = { roll_number: "", name: "", email: "", department: "", semester: "1" };

function StudentForm({
  initial,
  onSubmit,
  onCancel,
  busy,
  submitLabel,
}: {
  initial: typeof EMPTY_STUDENT;
  onSubmit: (input: StudentInput) => void;
  onCancel: () => void;
  busy: boolean;
  submitLabel: string;
}) {
  const [form, setForm] = useState(initial);
  const set = (key: keyof typeof EMPTY_STUDENT) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));
  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit({ ...form, semester: Number(form.semester) });
  }
  return (
    <form className="inline-form" onSubmit={submit}>
      <label>
        Roll number
        <Input value={form.roll_number} onChange={set("roll_number")} required maxLength={32} />
      </label>
      <label>
        Full name
        <Input value={form.name} onChange={set("name")} required maxLength={120} />
      </label>
      <label>
        Email
        <Input type="email" value={form.email} onChange={set("email")} required />
      </label>
      <label>
        Department
        <Input value={form.department} onChange={set("department")} required maxLength={120} />
      </label>
      <label>
        Semester
        <select className="native-select" value={form.semester} onChange={set("semester")}>
          {SEMESTERS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <div className="toggle-row">
        <Button type="submit" disabled={busy}>
          <Save />
          {busy ? "Saving…" : submitLabel}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          <X />
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function FacultyStudentsPage() {
  const { user } = useAuth();
  const client = useQueryClient();
  const overview = useOverview();
  const [q, setQ] = useState("");
  const [risk, setRisk] = useState("All");
  const [sort, setSort] = useState("roll");
  const [adding, setAdding] = useState(false);
  const students = useMemo(() => overview.data?.students ?? [], [overview.data]);
  const create = useMutation({
    mutationFn: facultyApi.createStudent,
    onSuccess: (s) => {
      toast.success(`${s.name} added`);
      setAdding(false);
      void client.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
  const data = useMemo(() => {
    const term = q.toLowerCase();
    return students
      .filter(
        (s) => s.name.toLowerCase().includes(term) || s.roll_number.toLowerCase().includes(term),
      )
      .filter(
        (s) =>
          risk === "All" ||
          (risk === "none" ? !s.latest_prediction : s.latest_prediction?.risk_level === risk),
      )
      .sort((a, b) =>
        sort === "prediction"
          ? (a.latest_prediction?.predicted_marks ?? 101) -
            (b.latest_prediction?.predicted_marks ?? 101)
          : sort === "risk"
            ? (a.latest_prediction ? RISK_ORDER[a.latest_prediction.risk_level] : 3) -
              (b.latest_prediction ? RISK_ORDER[b.latest_prediction.risk_level] : 3)
            : a.roll_number.localeCompare(b.roll_number),
      );
  }, [students, q, risk, sort]);

  return (
    <>
      <PageHeader
        title="Students"
        description="All student records with their latest prediction."
        actions={
          !adding && (
            <Button onClick={() => setAdding(true)}>
              <Plus />
              Add student
            </Button>
          )
        }
      />
      {adding && (
        <StudentForm
          initial={{ ...EMPTY_STUDENT, department: user?.department ?? "" }}
          busy={create.isPending}
          onSubmit={(input) => create.mutate(input)}
          onCancel={() => setAdding(false)}
          submitLabel="Add student"
        />
      )}
      <div className="table-tools">
        <label className="search">
          <Search />
          <Input
            placeholder="Search by student or roll number"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
        <label>
          <Filter />
          Risk
          <select value={risk} onChange={(e) => setRisk(e.target.value)}>
            <option value="All">All</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="none">No prediction</option>
          </select>
        </label>
        <label>
          Sort by
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="roll">Roll number</option>
            <option value="prediction">Prediction (lowest first)</option>
            <option value="risk">Risk (highest first)</option>
          </select>
        </label>
      </div>
      <Loadable
        isLoading={overview.isLoading}
        error={overview.error}
        onRetry={() => void overview.refetch()}
      >
        <div className="result-count">
          Showing {data.length} of {students.length} students
        </div>
        <StudentsTable items={data} benchmark={null} />
      </Loadable>
    </>
  );
}

// --- student detail ------------------------------------------------------------------------------

const INPUT_FIELDS: [keyof PredictionInputs, string][] = [
  ["attendance", "Attendance %"],
  ["internal1", "Internal 1 %"],
  ["internal2", "Internal 2 %"],
  ["assignment", "Assignment %"],
];

function PredictPanel({
  studentId,
  records,
  attendance,
  onDone,
}: {
  studentId: number;
  records: SubjectRecord[];
  attendance: number | null;
  onDone: (p: Prediction) => void;
}) {
  const fromRecords = useMemo(() => inputsFromRecords(records, attendance), [records, attendance]);
  const [stage, setStage] = useState<Stage>(
    fromRecords.internal2 !== undefined ? "stage2" : "stage1",
  );
  const [source, setSource] = useState<"records" | "manual">("records");
  const [manual, setManual] = useState<Record<string, string>>({});
  useEffect(() => {
    setManual(
      Object.fromEntries(
        INPUT_FIELDS.map(([k]) => [k, fromRecords[k] !== undefined ? String(fromRecords[k]) : ""]),
      ),
    );
  }, [fromRecords]);
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => {
      if (source === "records") return predictionApi.predict(studentId, stage);
      const n = (k: string) => Number(manual[k]);
      const inputs: PredictionInputs = {
        attendance: n("attendance"),
        internal1: n("internal1"),
        assignment: n("assignment"),
      };
      if (stage === "stage2") inputs.internal2 = n("internal2");
      return predictionApi.predict(studentId, stage, inputs);
    },
    onSuccess: (p) => {
      toast.success("Prediction saved");
      onDone(p);
      void client.invalidateQueries({ queryKey: ["history", studentId] });
      void client.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
  const fields = INPUT_FIELDS.filter(([k]) => stage === "stage2" || k !== "internal2");
  const manualValid = fields.every(
    ([k]) => manual[k] !== "" && Number(manual[k]) >= 0 && Number(manual[k]) <= 100,
  );
  return (
    <section className="predict-panel">
      <SectionTitle
        title="Run a prediction"
        description="The result is saved to this student's history with its explanation."
      />
      <div className="predict-controls">
        <label>
          Stage
          <div className="toggle-row">
            {(["stage1", "stage2"] as Stage[]).map((s) => (
              <button
                type="button"
                key={s}
                className={stage === s ? "selected" : ""}
                onClick={() => setStage(s)}
              >
                {s === "stage1" ? "Stage 1" : "Stage 2"}
              </button>
            ))}
          </div>
        </label>
        <label>
          Inputs
          <div className="toggle-row">
            <button
              type="button"
              className={source === "records" ? "selected" : ""}
              onClick={() => setSource("records")}
            >
              From stored records
            </button>
            <button
              type="button"
              className={source === "manual" ? "selected" : ""}
              onClick={() => setSource("manual")}
            >
              Enter manually
            </button>
          </div>
        </label>
      </div>
      {source === "records" ? (
        <p className="field-hint">
          Uses attendance and each assessment's percentage averaged across subjects:{" "}
          {fields
            .map(
              ([k, label]) =>
                `${label.replace(" %", "")} ${fromRecords[k] !== undefined ? `${fromRecords[k]}%` : "missing"}`,
            )
            .join(" · ")}
        </p>
      ) : (
        <div className="manual-inputs">
          {fields.map(([k, label]) => (
            <label key={k}>
              {label}
              <Input
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={manual[k] ?? ""}
                onChange={(e) => setManual((m) => ({ ...m, [k]: e.target.value }))}
              />
            </label>
          ))}
        </div>
      )}
      <Button
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending || (source === "manual" && !manualValid)}
      >
        {mutation.isPending ? "Predicting…" : `Predict ${STAGE_LABEL[stage].toLowerCase()}`}
      </Button>
    </section>
  );
}

export function StudentDetailPage({ id }: { id: string }) {
  const studentId = Number(id);
  const client = useQueryClient();
  const nav = useNavigate();
  const student = useQuery({
    queryKey: ["student", studentId],
    queryFn: () => facultyApi.student(studentId),
    enabled: Number.isInteger(studentId),
  });
  const academic = useQuery({
    queryKey: ["academic", studentId],
    queryFn: () => facultyApi.academic(studentId),
    enabled: !!student.data,
  });
  const history = useQuery({
    queryKey: ["history", studentId],
    queryFn: () => studentApi.history(studentId),
    enabled: !!student.data,
  });
  const monitoring = useQuery({
    queryKey: ["monitoring", studentId],
    queryFn: () => facultyApi.monitoring(studentId),
    enabled: !!student.data,
  });
  const benchmark = useQuery({
    queryKey: ["benchmark", student.data?.department, student.data?.semester],
    queryFn: () => facultyApi.benchmark(student.data!.department, student.data!.semester),
    enabled: !!student.data,
  });
  const [editing, setEditing] = useState(false);
  const [shown, setShown] = useState<Prediction | null>(null);
  const [status, setStatus] = useState<MonitoringStatus>("Not Contacted");
  const [notes, setNotes] = useState("");
  useEffect(() => {
    if (monitoring.data) {
      setStatus(monitoring.data.status);
      setNotes(monitoring.data.notes ?? "");
    }
  }, [monitoring.data]);

  const update = useMutation({
    mutationFn: (input: StudentInput) => facultyApi.updateStudent(studentId, input),
    onSuccess: () => {
      toast.success("Student updated");
      setEditing(false);
      void client.invalidateQueries({ queryKey: ["student", studentId] });
      void client.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: () => facultyApi.deleteStudent(studentId),
    onSuccess: () => {
      toast.success("Student deleted");
      void client.invalidateQueries({ queryKey: ["overview"] });
      nav({ to: "/faculty/students" });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
  const saveMonitoring = useMutation({
    mutationFn: () => facultyApi.saveMonitoring(studentId, status, notes),
    onSuccess: () => {
      toast.success("Monitoring record saved");
      void client.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });

  const queries = [student, academic, history, monitoring];
  const s = student.data;
  const items = history.data ?? [];
  const latest = shown ?? items[0];
  const bench = benchmark.data?.benchmark_percentage ?? null;
  const gap = latest && bench !== null ? latest.predicted_marks - bench : null;

  return (
    <Loadable
      isLoading={queries.some((x) => x.isLoading)}
      error={queries.find((x) => x.error)?.error ?? null}
      onRetry={() => queries.forEach((x) => void x.refetch())}
    >
      {s && (
        <>
          <PageHeader
            title={s.name}
            description={`${s.roll_number} · ${s.department} · Semester ${s.semester} · ${s.has_account ? "has an account" : "no account yet"}`}
            actions={
              <>
                <Button variant="outline" asChild>
                  <Link to="/faculty/students">
                    <ChevronLeft />
                    Back
                  </Link>
                </Button>
                <Button variant="outline" onClick={() => setEditing((v) => !v)}>
                  <Pencil />
                  Edit
                </Button>
                <Button
                  variant="outline"
                  disabled={remove.isPending}
                  onClick={() => {
                    if (
                      window.confirm(
                        `Delete ${s.name} (${s.roll_number}) and all their records and predictions? This cannot be undone.`,
                      )
                    )
                      remove.mutate();
                  }}
                >
                  <Trash2 />
                  Delete
                </Button>
              </>
            }
          />
          {editing && (
            <StudentForm
              initial={{
                roll_number: s.roll_number,
                name: s.name,
                email: s.email,
                department: s.department,
                semester: String(s.semester),
              }}
              busy={update.isPending}
              onSubmit={(input) => update.mutate(input)}
              onCancel={() => setEditing(false)}
              submitLabel="Save changes"
            />
          )}
          <div className="stats-row">
            <Stat
              label="Latest prediction"
              value={pct(latest?.predicted_marks, 1)}
              detail={
                latest
                  ? `${STAGE_LABEL[latest.stage]} · ${formatDate(latest.created_at)}`
                  : "No prediction yet"
              }
            />
            <Stat
              label="Class benchmark"
              value={pct(bench)}
              detail={
                bench === null
                  ? "Not set for this semester"
                  : `${s.department}, semester ${s.semester}`
              }
            />
            <Stat
              label="Gap"
              value={gap === null ? "—" : `${gap >= 0 ? "+" : ""}${gap.toFixed(1)} pp`}
              tone={gap === null ? "default" : gap < 0 ? "danger" : "success"}
            />
            <Stat
              label="Attendance"
              value={pct(academic.data?.attendance_percentage, 1)}
              detail={`Semester ${s.semester}`}
            />
          </div>
          <PredictPanel
            studentId={s.id}
            records={academic.data?.records ?? []}
            attendance={academic.data?.attendance_percentage ?? null}
            onDone={setShown}
          />
          {latest && (
            <PredictionResult
              result={latest}
              title={shown ? "New prediction" : "Latest prediction"}
            />
          )}
          <section className="detail-grid" style={{ marginTop: 24 }}>
            <div className="plain-section">
              <SectionTitle title="Prediction history" />
              {items.length ? (
                <PredictionChart
                  data={[...items].reverse().map((p) => ({
                    stage: `${STAGE_LABEL[p.stage]} · ${formatDate(p.created_at)}`,
                    value: p.predicted_marks,
                  }))}
                  target={bench}
                  targetLabel="Benchmark"
                />
              ) : (
                <p className="field-hint">No predictions yet.</p>
              )}
            </div>
            <div className="monitor-panel">
              <SectionTitle title="Monitoring" description="Record the current follow-up state." />
              <label>
                Status
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value as MonitoringStatus)}
                >
                  {MONITORING_STATUSES.map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </label>
              <label>
                Faculty notes
                <textarea
                  rows={6}
                  maxLength={2000}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </label>
              <Button onClick={() => saveMonitoring.mutate()} disabled={saveMonitoring.isPending}>
                <Save />
                {saveMonitoring.isPending ? "Saving…" : "Save monitoring"}
              </Button>
            </div>
          </section>
          <section className="plain-section">
            <SectionTitle
              title="Subject-wise performance"
              description={`Semester ${academic.data?.semester ?? s.semester}`}
              aside={
                <Button variant="ghost" size="sm" asChild>
                  <Link to="/faculty/academic-data" search={{ student: s.id }}>
                    <FileSpreadsheet />
                    Edit marks
                  </Link>
                </Button>
              }
            />
            {academic.data?.records.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Subject</th>
                      <th>Internal 1</th>
                      <th>Internal 2</th>
                      <th>Assignment</th>
                      <th className="numeric">Test average</th>
                    </tr>
                  </thead>
                  <tbody>
                    {academic.data.records.map((r) => (
                      <tr key={r.subject_name}>
                        <td>
                          <b>{r.subject_name}</b>
                        </td>
                        <td>{markLabel(r.internal1)}</td>
                        <td>{markLabel(r.internal2)}</td>
                        <td>{markLabel(r.assignment)}</td>
                        <td className="numeric">
                          <b>{pct(subjectAverage(r))}</b>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="field-hint">No marks recorded for this semester.</p>
            )}
          </section>
        </>
      )}
    </Loadable>
  );
}

// --- academic data entry -------------------------------------------------------------------------

type MarkDraft = { obtained: string; maximum: string };
type RowDraft = {
  subject_name: string;
  internal1: MarkDraft;
  internal2: MarkDraft;
  assignment: MarkDraft;
};
const ASSESSMENTS = ["internal1", "internal2", "assignment"] as const;
const emptyMark = (): MarkDraft => ({ obtained: "", maximum: "" });
const toDraft = (m: Mark | null): MarkDraft =>
  m ? { obtained: String(m.obtained), maximum: String(m.maximum) } : emptyMark();

function fromDraft(m: MarkDraft, label: string): Mark | null {
  if (m.obtained === "" && m.maximum === "") return null;
  if (m.obtained === "" || m.maximum === "")
    throw new Error(`${label}: enter both obtained and maximum marks, or neither.`);
  const obtained = Number(m.obtained),
    maximum = Number(m.maximum);
  if (!(maximum > 0) || obtained < 0 || obtained > maximum)
    throw new Error(`${label}: obtained must be between 0 and the maximum (> 0).`);
  return { obtained, maximum };
}

export function AcademicDataPage({ initialStudentId }: { initialStudentId?: number }) {
  const client = useQueryClient();
  const overview = useOverview();
  const students = overview.data?.students ?? [];
  const [studentId, setStudentId] = useState<number | undefined>(initialStudentId);
  const selected = students.find((s) => s.id === studentId);
  const [semester, setSemester] = useState<number | undefined>(undefined);
  const activeSemester = semester ?? selected?.semester;
  const academic = useQuery({
    queryKey: ["academic", studentId, activeSemester],
    queryFn: () => facultyApi.academic(studentId!, activeSemester),
    enabled: !!studentId && !!activeSemester,
  });
  const [rows, setRows] = useState<RowDraft[]>([]);
  const [attendance, setAttendance] = useState("");
  useEffect(() => {
    if (!academic.data) return;
    setRows(
      academic.data.records.map((r) => ({
        subject_name: r.subject_name,
        internal1: toDraft(r.internal1),
        internal2: toDraft(r.internal2),
        assignment: toDraft(r.assignment),
      })),
    );
    setAttendance(
      academic.data.attendance_percentage === null
        ? ""
        : String(academic.data.attendance_percentage),
    );
  }, [academic.data]);

  const save = useMutation({
    mutationFn: () => {
      const records: SubjectRecord[] = rows.map((r, i) => {
        if (!r.subject_name.trim()) throw new Error(`Row ${i + 1}: enter a subject name.`);
        return {
          subject_name: r.subject_name.trim(),
          internal1: fromDraft(r.internal1, `${r.subject_name} Internal 1`),
          internal2: fromDraft(r.internal2, `${r.subject_name} Internal 2`),
          assignment: fromDraft(r.assignment, `${r.subject_name} assignment`),
        };
      });
      const att = attendance === "" ? null : Number(attendance);
      if (att !== null && !(att >= 0 && att <= 100))
        throw new Error("Attendance must be between 0 and 100.");
      return facultyApi.saveAcademic(studentId!, {
        semester: activeSemester!,
        attendance_percentage: att,
        records,
      });
    },
    onSuccess: () => {
      toast.success("Academic records saved");
      void client.invalidateQueries({ queryKey: ["academic", studentId] });
      void client.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
  const updateMark = (
    i: number,
    key: (typeof ASSESSMENTS)[number],
    part: keyof MarkDraft,
    value: string,
  ) =>
    setRows((rs) =>
      rs.map((r, n) => (n === i ? { ...r, [key]: { ...r[key], [part]: value } } : r)),
    );

  return (
    <>
      <PageHeader
        title="Academic data"
        description="Enter subject marks (obtained and maximum) and attendance for one student and semester."
        actions={
          studentId && (
            <Button
              onClick={() =>
                setRows((r) => [
                  ...r,
                  {
                    subject_name: "",
                    internal1: emptyMark(),
                    internal2: emptyMark(),
                    assignment: emptyMark(),
                  },
                ])
              }
            >
              <Plus />
              Add subject
            </Button>
          )
        }
      />
      <Loadable
        isLoading={overview.isLoading}
        error={overview.error}
        onRetry={() => void overview.refetch()}
      >
        <div className="student-selector">
          <label>
            Student
            <select
              value={studentId ?? ""}
              onChange={(e) => {
                setStudentId(e.target.value ? Number(e.target.value) : undefined);
                setSemester(undefined);
              }}
            >
              <option value="">Choose a student…</option>
              {students.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} · {s.roll_number}
                </option>
              ))}
            </select>
          </label>
          {selected && (
            <label>
              Semester
              <select value={activeSemester} onChange={(e) => setSemester(Number(e.target.value))}>
                {SEMESTERS.map((s) => (
                  <option key={s} value={s}>
                    Semester {s}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {!studentId ? (
          <div className="empty-panel">
            <strong>Choose a student</strong>
            <p>Pick a student to view or edit their marks.</p>
          </div>
        ) : (
          <Loadable
            isLoading={academic.isLoading}
            error={academic.error}
            onRetry={() => void academic.refetch()}
          >
            <section className="plain-section">
              <SectionTitle
                title="Subject records"
                description="Leave an assessment blank until it has been held. Saving replaces this semester's records with the table below."
              />
              <label className="inline-field">
                Overall attendance %
                <div className="suffix-input">
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={attendance}
                    onChange={(e) => setAttendance(e.target.value)}
                  />
                  <span>%</span>
                </div>
              </label>
              <div className="table-wrap entry-table">
                <table>
                  <thead>
                    <tr>
                      <th rowSpan={2}>Subject name</th>
                      <th colSpan={2}>Internal 1</th>
                      <th colSpan={2}>Internal 2</th>
                      <th colSpan={2}>Assignment</th>
                      <th rowSpan={2}></th>
                    </tr>
                    <tr>
                      <th>Obtained</th>
                      <th>Maximum</th>
                      <th>Obtained</th>
                      <th>Maximum</th>
                      <th>Obtained</th>
                      <th>Maximum</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <tr key={i}>
                        <td>
                          <Input
                            value={r.subject_name}
                            onChange={(e) =>
                              setRows((rs) =>
                                rs.map((x, n) =>
                                  n === i ? { ...x, subject_name: e.target.value } : x,
                                ),
                              )
                            }
                            placeholder="Subject name"
                          />
                        </td>
                        {ASSESSMENTS.flatMap((key) => [
                          <td key={`${key}o`}>
                            <Input
                              type="number"
                              min="0"
                              step="0.01"
                              value={r[key].obtained}
                              placeholder="—"
                              onChange={(e) => updateMark(i, key, "obtained", e.target.value)}
                            />
                          </td>,
                          <td key={`${key}m`}>
                            <Input
                              type="number"
                              min="0"
                              step="0.01"
                              value={r[key].maximum}
                              placeholder="Maximum"
                              onChange={(e) => updateMark(i, key, "maximum", e.target.value)}
                            />
                          </td>,
                        ])}
                        <td>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setRows((rs) => rs.filter((_, n) => n !== i))}
                            aria-label="Remove subject"
                          >
                            <Trash2 />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="form-footer">
                <span>{rows.length} subject records</span>
                <Button onClick={() => save.mutate()} disabled={save.isPending}>
                  <Save />
                  {save.isPending ? "Saving…" : "Save changes"}
                </Button>
              </div>
            </section>
          </Loadable>
        )}
      </Loadable>
    </>
  );
}

// --- upload (not connected yet) ------------------------------------------------------------------

export function UploadPage() {
  return (
    <>
      <PageHeader title="Upload academic data" description="Bulk CSV/Excel upload." />
      <div className="empty-panel">
        <strong>Bulk upload is not connected to the new backend yet</strong>
        <p>
          Until it is, enter marks and attendance per student on the Academic Data page. Every value
          entered there is validated and saved to the database.
        </p>
        <Button asChild>
          <Link to="/faculty/academic-data">
            <FileSpreadsheet />
            Go to Academic Data
          </Link>
        </Button>
      </div>
    </>
  );
}

// --- benchmark -----------------------------------------------------------------------------------

export function BenchmarkPage() {
  const { user } = useAuth();
  const client = useQueryClient();
  const all = useOverview();
  const departments = useMemo(
    () => Array.from(new Set((all.data?.students ?? []).map((s) => s.department))).sort(),
    [all.data],
  );
  const [department, setDepartment] = useState(user?.department ?? "");
  const [semester, setSemester] = useState(1);
  const dept = department || departments[0] || "";
  const benchmark = useQuery({
    queryKey: ["benchmark", dept, semester],
    queryFn: () => facultyApi.benchmark(dept, semester),
    enabled: !!dept,
  });
  const cohort = useOverview(dept || undefined, semester);
  const [value, setValue] = useState<number | null>(null);
  useEffect(() => setValue(null), [dept, semester]);
  const current = value ?? benchmark.data?.benchmark_percentage ?? 60;
  const predicted = (cohort.data?.students ?? []).filter((s) => s.latest_prediction);
  const below = predicted.filter((s) => s.latest_prediction!.predicted_marks < current);
  const save = useMutation({
    mutationFn: () => facultyApi.saveBenchmark(dept, semester, current),
    onSuccess: () => {
      toast.success("Benchmark saved");
      void client.invalidateQueries({ queryKey: ["benchmark"] });
      void client.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
  return (
    <>
      <PageHeader
        title="Performance benchmark"
        description="Set the class-level final performance threshold for a department and semester."
      />
      <div className="table-tools">
        <label>
          Department
          <select value={dept} onChange={(e) => setDepartment(e.target.value)}>
            {Array.from(new Set([...departments, ...(dept ? [dept] : [])])).map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </label>
        <label>
          Semester
          <select value={semester} onChange={(e) => setSemester(Number(e.target.value))}>
            {SEMESTERS.map((s) => (
              <option key={s} value={s}>
                Semester {s}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div style={{ height: 16 }} />
      {!dept ? (
        <div className="empty-panel">
          <strong>No departments yet</strong>
          <p>Add students first, or set your department on your account.</p>
        </div>
      ) : (
        <Loadable
          isLoading={benchmark.isLoading || cohort.isLoading}
          error={benchmark.error ?? cohort.error}
          onRetry={() => {
            void benchmark.refetch();
            void cohort.refetch();
          }}
        >
          <section className="benchmark-layout">
            <div className="benchmark-control">
              <SectionTitle
                title="Class benchmark"
                description={
                  benchmark.data?.benchmark_percentage == null
                    ? "No benchmark saved yet for this semester."
                    : "Students below this percentage are flagged for review."
                }
              />
              <label>
                Benchmark percentage
                <div className="suffix-input">
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={current}
                    onChange={(e) => setValue(Number(e.target.value))}
                  />
                  <span>%</span>
                </div>
              </label>
              <input
                className="benchmark-slider"
                type="range"
                min="30"
                max="95"
                value={current}
                onChange={(e) => setValue(Number(e.target.value))}
              />
              <Button
                onClick={() => save.mutate()}
                disabled={save.isPending || !(current >= 0 && current <= 100)}
              >
                <Save />
                {save.isPending ? "Saving…" : "Save benchmark"}
              </Button>
            </div>
            <div className="benchmark-distribution">
              <div>
                <span>Below benchmark</span>
                <strong>
                  {below.length} / {predicted.length}
                </strong>
                <small>Students with a prediction</small>
              </div>
              <div>
                <span>At or above</span>
                <strong>
                  {predicted.length - below.length} / {predicted.length}
                </strong>
                <small>Currently on track</small>
              </div>
              {predicted.length > 0 && (
                <Meter
                  value={Math.round(((predicted.length - below.length) / predicted.length) * 100)}
                  label="On track"
                />
              )}
            </div>
          </section>
          <section className="plain-section" style={{ marginTop: 24 }}>
            <SectionTitle title="Students currently below this benchmark" />
            <StudentsTable items={below} benchmark={current} compact />
          </section>
        </Loadable>
      )}
    </>
  );
}

// --- monitoring ----------------------------------------------------------------------------------

function MonitoringRow({ s, benchmark }: { s: OverviewStudent; benchmark: number | null }) {
  const client = useQueryClient();
  const [status, setStatus] = useState<MonitoringStatus>(s.monitoring_status ?? "Not Contacted");
  const [notes, setNotes] = useState(s.monitoring_notes ?? "");
  const save = useMutation({
    mutationFn: () => facultyApi.saveMonitoring(s.id, status, notes),
    onSuccess: () => {
      toast.success(`Saved for ${s.name}`);
      void client.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (e) => toast.error(getApiErrorMessage(e)),
  });
  const p = s.latest_prediction!;
  return (
    <tr>
      <td>
        <b>{s.name}</b>
        <small>
          {s.department} · Sem {s.semester}
        </small>
      </td>
      <td className="mono">{s.roll_number}</td>
      <td className="numeric">
        <b>{p.predicted_marks.toFixed(1)}%</b>
      </td>
      <td>
        <RiskBadge risk={p.risk_level} />
      </td>
      <td className="numeric">
        {benchmark === null ? (
          "—"
        ) : (
          <span className={p.predicted_marks < benchmark ? "danger-text" : ""}>
            {(p.predicted_marks - benchmark).toFixed(1)} pp
          </span>
        )}
      </td>
      <td>
        <select value={status} onChange={(e) => setStatus(e.target.value as MonitoringStatus)}>
          {MONITORING_STATUSES.map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
      </td>
      <td className="note-cell">
        <Input
          value={notes}
          maxLength={2000}
          placeholder="Add a note"
          onChange={(e) => setNotes(e.target.value)}
        />
      </td>
      <td>
        <Button size="sm" variant="outline" onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save"}
        </Button>
      </td>
    </tr>
  );
}

export function MonitoringPage() {
  const filters = useFilters();
  const overview = useOverview(filters.department || undefined, filters.semester);
  const all = useOverview();
  const departments = useMemo(
    () => Array.from(new Set((all.data?.students ?? []).map((s) => s.department))),
    [all.data],
  );
  const benchmark = overview.data?.benchmark_percentage ?? null;
  const rows = (overview.data?.students ?? []).filter((s) => needsAttention(s, benchmark));
  return (
    <>
      <PageHeader
        title="Student monitoring"
        description="Follow up with students at medium or high risk, or below the benchmark."
      />
      <CohortFilters {...filters} departments={departments} />
      <Loadable
        isLoading={overview.isLoading}
        error={overview.error}
        onRetry={() => void overview.refetch()}
      >
        <div className="monitor-summary">
          <span>
            <b>{rows.length}</b> students need attention
          </span>
          <span>
            <b>{rows.filter((r) => r.monitoring_status === "Under Monitoring").length}</b> under
            monitoring
          </span>
          <span>
            <b>{rows.filter((r) => r.monitoring_status === "Improved").length}</b> improved
          </span>
        </div>
        {rows.length === 0 ? (
          <div className="empty-panel">
            <strong>Nobody needs follow-up right now</strong>
            <p>
              Students appear here when their latest prediction is medium or high risk, or below the
              benchmark.
            </p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Roll number</th>
                  <th className="numeric">Prediction</th>
                  <th>Risk</th>
                  <th className="numeric">Gap</th>
                  <th>Monitoring status</th>
                  <th>Note</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <MonitoringRow key={s.id} s={s} benchmark={benchmark} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="inline-notice">
          <Info />
          Benchmark gaps appear when a department and semester with a saved benchmark are selected.
        </div>
      </Loadable>
    </>
  );
}

export function FacultyProfilePage() {
  const { user } = useAuth();
  const initials =
    user?.name
      .split(" ")
      .map((x) => x[0])
      .slice(0, 2)
      .join("") ?? "";
  return (
    <>
      <PageHeader title="Profile" description="Your account details." />
      <section className="profile-sheet">
        <div className="profile-heading">
          <div className="profile-avatar">{initials}</div>
          <div>
            <h2>{user?.name}</h2>
            <span>
              {user?.role === "admin" ? "Administrator" : "Faculty"}
              {user?.department ? ` · ${user.department}` : ""}
            </span>
          </div>
        </div>
        <dl>
          <div>
            <dt>Employee ID</dt>
            <dd>{user?.employee_id ?? "—"}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{user?.email}</dd>
          </div>
          <div>
            <dt>Department</dt>
            <dd>{user?.department ?? "—"}</dd>
          </div>
          <div>
            <dt>Role</dt>
            <dd>{user?.role === "admin" ? "Administrator" : "Faculty"}</dd>
          </div>
        </dl>
      </section>
    </>
  );
}
