import { api, setAccessToken } from "./api";
import type { User } from "./types";

export type AuthUser = User;

export type RegisterInput = {
  name: string;
  email: string;
  password: string;
  roll_number: string;
  department: string;
  semester: number;
};

type TokenResponse = { access_token: string; token_type: "bearer"; expires_in: number; user: User };

export const authApi = {
  async login(identifier: string, password: string) {
    const response = await api.post<TokenResponse>("/api/auth/login", { identifier, password });
    setAccessToken(response.data.access_token);
    return response.data.user;
  },
  async register(input: RegisterInput) {
    const response = await api.post<User>("/api/auth/register", input);
    return response.data;
  },
  async logout() {
    try {
      await api.post("/api/auth/logout");
    } finally {
      setAccessToken(null);
    }
  },
  async getCurrentUser() {
    const response = await api.get<User>("/api/auth/me");
    return response.data;
  },
};

/** Admins use the faculty workspace. */
export const workspaceOf = (user: Pick<User, "role">) =>
  user.role === "student" ? "student" : "faculty";
