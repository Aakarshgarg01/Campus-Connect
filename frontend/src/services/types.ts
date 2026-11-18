// Types mirroring the FastAPI response models (backend/app/schemas).

export type Role = "admin" | "faculty" | "student";
export type Workspace = "student" | "faculty";
export type Stage = "stage1" | "stage2";
export type RiskLevel = "low" | "medium" | "high";
export type MonitoringStatus =
  "Not Contacted" | "Contacted" | "Counselling Done" | "Under Monitoring" | "Improved";

export const MONITORING_STATUSES: MonitoringStatus[] = [
  "Not Contacted",
  "Contacted",
  "Counselling Done",
  "Under Monitoring",
  "Improved",
];

export type User = {
  id: number;
  name: string;
  email: string;
  role: Role;
  employee_id: string | null;
  department: string | null;
  student_id: number | null;
  roll_number: string | null;
  created_at: string;
};

export type Student = {
  id: number;
  roll_number: string;
  name: string;
  email: string;
  department: string;
  semester: number;
  has_account: boolean;
  created_at: string;
  updated_at: string;
};

export type StudentInput = Pick<
  Student,
  "roll_number" | "name" | "email" | "department" | "semester"
>;

export type Mark = { obtained: number; maximum: number };
export type SubjectRecord = {
  id?: number;
  subject_name: string;
  internal1: Mark | null;
  internal2: Mark | null;
  assignment: Mark | null;
};
export type AcademicData = {
  student_id: number;
  semester: number;
  attendance_percentage: number | null;
  records: SubjectRecord[];
};

export type Interval = { low: number; high: number; description: string };
export type Contribution = {
  feature: string;
  label: string;
  value: number;
  shap_value: number;
  direction: "increases" | "decreases" | "neutral";
};
export type ShapExplanation = {
  method: string;
  base_value: number;
  raw_prediction: number;
  additivity_error: number;
  contributions: Contribution[];
  note: string;
};
export type RecommendationItem = {
  priority: number;
  feature: string;
  label: string;
  current_value: number;
  reference_value: number;
  shap_value: number;
  finding: string;
  action: string;
  estimated_effect: { change_to: number; predicted_change: number; text: string };
};
export type Recommendations = {
  summary: string;
  risk_note: string;
  items: RecommendationItem[];
  strengths: { feature: string; label: string; text: string; shap_value: number }[];
  method: string;
};

export type PredictionInputs = {
  attendance: number;
  internal1: number;
  internal2?: number;
  assignment: number;
};

export type Prediction = {
  id: number;
  student_id: number;
  semester: number;
  stage: Stage;
  inputs: Record<string, number>;
  input_source: "manual" | "records" | null;
  predicted_marks: number;
  risk_level: RiskLevel;
  interval: Interval | null;
  warnings: string[];
  shap_explanation: ShapExplanation | null;
  recommendations: Recommendations | null;
  model_version: string;
  created_by_user_id: number | null;
  created_at: string;
  disclaimer: string;
};

export type Simulation = Omit<
  Prediction,
  "id" | "student_id" | "semester" | "input_source" | "created_by_user_id" | "created_at"
> & { simulation_only: true };

export type Target = { student_id: number; semester: number; target_percentage: number | null };
export type Benchmark = {
  department: string;
  semester: number;
  benchmark_percentage: number | null;
  updated_at: string | null;
};
export type Monitoring = {
  student_id: number;
  semester: number;
  status: MonitoringStatus;
  notes: string | null;
  updated_at: string | null;
};

export type OverviewStudent = {
  id: number;
  roll_number: string;
  name: string;
  department: string;
  semester: number;
  attendance_percentage: number | null;
  latest_prediction: {
    id: number;
    stage: Stage;
    predicted_marks: number;
    risk_level: RiskLevel;
    created_at: string;
  } | null;
  monitoring_status: MonitoringStatus | null;
  monitoring_notes: string | null;
};
export type FacultyOverview = {
  department: string | null;
  semester: number | null;
  benchmark_percentage: number | null;
  total_students: number;
  with_prediction: number;
  below_benchmark: number | null;
  risk_counts: Record<RiskLevel, number>;
  distribution: { band: string; count: number }[];
  average_prediction: number | null;
  students: OverviewStudent[];
};

export type FeatureImportance = {
  stages: {
    stage: Stage;
    model_version: string;
    method: string;
    computed_on: string;
    base_value: number;
    values: { feature: string; label: string; mean_abs_shap: number; share: number }[];
  }[];
  note: string;
};

export const FEATURE_KEYS = {
  attendance: "attendance_pct",
  internal1: "internal1_pct",
  internal2: "internal2_pct",
  assignment: "assignment_pct",
} as const;

export const STAGE_LABEL: Record<Stage, string> = {
  stage1: "After Internal 1",
  stage2: "After Internal 2",
};
