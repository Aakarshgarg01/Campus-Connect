import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

// Base URL of the FastAPI backend, from VITE_API_BASE_URL (see .env.example).
const apiBaseUrl = import.meta.env["VITE_API_BASE_URL"] || "http://localhost:8000";

export const api = axios.create({
  baseURL: apiBaseUrl.replace(/\/+$/, ""),
  // Generous timeout: free hosting tiers can take a while to wake up after idling.
  timeout: 30000,
  // Sends/receives the httpOnly auth cookie set by POST /api/auth/login.
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

// The JWT from the login response is also kept in memory and sent as a Bearer token, so
// requests still authenticate where the browser blocks cross-site cookies.
let accessToken: string | null = null;
export function setAccessToken(token: string | null) {
  accessToken = token;
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.set("Authorization", `Bearer ${accessToken}`);
  return config;
});

// Retry safe (GET) requests that fail because the server is waking up or unreachable.
type RetryConfig = InternalAxiosRequestConfig & { retryCount?: number };
const RETRY_STATUSES = new Set([502, 503, 504]);
const MAX_RETRIES = 2;

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const config = error.config as RetryConfig | undefined;
  const status = error.response?.status;
  const retryable = !error.response || (status !== undefined && RETRY_STATUSES.has(status));
  const isModelUnavailable =
    (error.response?.data as { error?: { code?: string } } | undefined)?.error?.code ===
    "model_unavailable";
  if (!config || config.method !== "get" || !retryable || isModelUnavailable) throw error;
  config.retryCount = (config.retryCount ?? 0) + 1;
  if (config.retryCount > MAX_RETRIES) throw error;
  await new Promise((resolve) => setTimeout(resolve, 1500 * config.retryCount!));
  return api.request(config);
});
