import type { AcademicRecord, Mark } from "@/data/mock-data";
export const percent = (mark: Mark | null) => mark ? (mark.obtained / mark.maximum) * 100 : null;
export const subjectAverage = (r: AcademicRecord) => {
 const i1=percent(r.internal1) ?? 0; const i2=percent(r.internal2);
 return i2 === null ? i1 : (i1+i2)/2;
};
export const overallSubjectAverage = (items: AcademicRecord[]) => items.length ? items.reduce((sum,r)=>sum+subjectAverage(r),0)/items.length : 0;
export type Zone = "red" | "yellow" | "green";
export const classifyZone = (value:number, overall:number, tolerance=.1):Zone => value < overall*(1-tolerance) ? "red" : value > overall*(1+tolerance) ? "green" : "yellow";
export const zoneLabel = (z:Zone) => z === "red" ? "Needs significant improvement" : z === "yellow" ? "Requires continued effort" : "Performing well";
export const markLabel = (m:Mark|null) => m ? `${m.obtained} / ${m.maximum}` : "Not available";
