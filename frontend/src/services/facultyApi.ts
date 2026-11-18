import { api } from "./api";
import type {
  AcademicData,
  Benchmark,
  FacultyOverview,
  Monitoring,
  MonitoringStatus,
  Student,
  StudentInput,
  SubjectRecord,
} from "./types";

export const facultyApi = {
  async overview(params: { department?: string; semester?: number } = {}) {
    return (await api.get<FacultyOverview>("/api/faculty/overview", { params })).data;
  },
  async student(id: number) {
    return (await api.get<Student>(`/api/students/${id}`)).data;
  },
  async createStudent(input: StudentInput) {
    return (await api.post<Student>("/api/students/", input)).data;
  },
  async updateStudent(id: number, changes: Partial<StudentInput>) {
    return (await api.put<Student>(`/api/students/${id}`, changes)).data;
  },
  async deleteStudent(id: number) {
    await api.delete(`/api/students/${id}`);
  },
  async academic(id: number, semester?: number) {
    return (await api.get<AcademicData>(`/api/students/${id}/academic`, { params: { semester } }))
      .data;
  },
  async saveAcademic(
    id: number,
    data: { semester: number; attendance_percentage: number | null; records: SubjectRecord[] },
  ) {
    const records = data.records.map(({ subject_name, internal1, internal2, assignment }) => ({
      subject_name,
      internal1,
      internal2,
      assignment,
    }));
    return (await api.put<AcademicData>(`/api/students/${id}/academic`, { ...data, records })).data;
  },
  async monitoring(id: number) {
    return (await api.get<Monitoring>(`/api/students/${id}/monitoring`)).data;
  },
  async saveMonitoring(id: number, status: MonitoringStatus, notes: string) {
    return (await api.put<Monitoring>(`/api/students/${id}/monitoring`, { status, notes })).data;
  },
  async benchmark(department: string, semester: number) {
    return (await api.get<Benchmark>("/api/benchmarks", { params: { department, semester } })).data;
  },
  async saveBenchmark(department: string, semester: number, benchmark_percentage: number) {
    return (
      await api.put<Benchmark>("/api/benchmarks", { department, semester, benchmark_percentage })
    ).data;
  },
};
