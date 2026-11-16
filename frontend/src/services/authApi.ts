import { api } from "./api";

export type AuthRole = "student" | "faculty";
export type AuthUser = {
  id: string;
  name: string;
  email: string;
  role: AuthRole;
  department?: string;
  rollNumber?: string;
  employeeId?: string;
  semester?: number;
};

type AuthResponse = { user: AuthUser };

export const authApi = {
  async login(identifier: string, password: string) {
    const response = await api.post<AuthResponse>("/api/auth/login", { identifier, password });
    return response.data.user;
  },
  async logout() {
    await api.post("/api/auth/logout");
  },
  async getCurrentUser() {
    const response = await api.get<AuthResponse>("/api/auth/me");
    return response.data.user;
  },
};
