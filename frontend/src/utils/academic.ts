import type { Mark, PredictionInputs, SubjectRecord } from "@/services/types";

export const percent = (mark: Mark | null | undefined) =>
  mark && mark.maximum > 0 ? (mark.obtained / mark.maximum) * 100 : null;

/** Average of the available internal tests for one subject (null if none yet). */
export const subjectAverage = (r: SubjectRecord) => {
  const tests = [percent(r.internal1), percent(r.internal2)].filter((v): v is number => v !== null);
  return tests.length ? tests.reduce((a, b) => a + b, 0) / tests.length : null;
};

export const overallSubjectAverage = (items: SubjectRecord[]) => {
  const values = items.map(subjectAverage).filter((v): v is number => v !== null);
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
};

export type Zone = "red" | "yellow" | "green";
export const classifyZone = (value: number, overall: number, tolerance = 0.1): Zone =>
  value < overall * (1 - tolerance)
    ? "red"
    : value > overall * (1 + tolerance)
      ? "green"
      : "yellow";
export const zoneLabel = (z: Zone) =>
  z === "red"
    ? "Needs significant improvement"
    : z === "yellow"
      ? "Requires continued effort"
      : "Performing well";
export const markLabel = (m: Mark | null | undefined) =>
  m ? `${m.obtained} / ${m.maximum}` : "Not available";

/**
 * Model inputs from stored records, exactly as the backend computes them for a records-based
 * prediction: per-assessment percentage averaged across subjects (only if every subject has it).
 */
export function inputsFromRecords(
  records: SubjectRecord[],
  attendance: number | null,
): Partial<PredictionInputs> {
  const avg = (key: "internal1" | "internal2" | "assignment") => {
    const values = records.map((r) => percent(r[key]));
    if (!values.length || values.some((v) => v === null)) return undefined;
    return (
      Math.round(((values as number[]).reduce((a, b) => a + b, 0) / values.length) * 100) / 100
    );
  };
  const result: Partial<PredictionInputs> = {};
  if (attendance !== null) result.attendance = attendance;
  const i1 = avg("internal1");
  const i2 = avg("internal2");
  const a = avg("assignment");
  if (i1 !== undefined) result.internal1 = i1;
  if (i2 !== undefined) result.internal2 = i2;
  if (a !== undefined) result.assignment = a;
  return result;
}

export const pct = (n: number | null | undefined, digits = 0) =>
  n === null || n === undefined ? "—" : `${n.toFixed(digits)}%`;

export const formatDate = (iso: string) =>
  new Date(iso.endsWith("Z") ? iso : `${iso}Z`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

export const riskLabel = (risk: string) =>
  risk === "high" ? "High risk" : risk === "medium" ? "Medium risk" : "Low risk";
