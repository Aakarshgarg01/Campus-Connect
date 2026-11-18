import { api } from "./api";
import type { AcademicData, Benchmark, Prediction, Student, Target } from "./types";

export const studentApi = {
  async me() {
    return (await api.get<Student>("/api/students/me")).data;
  },
  async academic(studentId: number, semester?: number) {
    return (
      await api.get<AcademicData>(`/api/students/${studentId}/academic`, { params: { semester } })
    ).data;
  },
  async history(studentId: number) {
    return (
      await api.get<{ student_id: number; items: Prediction[] }>(
        `/api/predictions/history/${studentId}`,
      )
    ).data.items;
  },
  async target(studentId: number) {
    return (await api.get<Target>(`/api/students/${studentId}/target`)).data;
  },
  async saveTarget(studentId: number, target_percentage: number) {
    return (await api.put<Target>(`/api/students/${studentId}/target`, { target_percentage })).data;
  },
  async benchmark(department: string, semester: number) {
    return (await api.get<Benchmark>("/api/benchmarks", { params: { department, semester } })).data;
  },
};
