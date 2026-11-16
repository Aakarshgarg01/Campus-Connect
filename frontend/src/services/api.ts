import axios from "axios";
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

export const api = axios.create({
  baseURL: apiBaseUrl.replace(/\/+$/, ""),
  timeout: 10000,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});
export const mockDelay = <T>(value: T, delay = 250) =>
  new Promise<T>((resolve) => setTimeout(() => resolve(structuredClone(value)), delay));
