import axios from "axios";

// Backend error format: { error: { code, message, details }, request_id }
type ApiErrorBody = {
  error?: { code?: string; message?: string; details?: unknown };
};

export function getApiErrorStatus(error: unknown) {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

export function getApiErrorCode(error: unknown) {
  return axios.isAxiosError<ApiErrorBody>(error) ? error.response?.data?.error?.code : undefined;
}

function validationDetails(details: unknown): string | null {
  if (!Array.isArray(details) || details.length === 0) return null;
  const messages = details
    .map((d) => {
      if (!d || typeof d !== "object") return null;
      const { field, message } = d as { field?: string; message?: string };
      const name = field?.split(".").slice(1).join(".") || "";
      const text = (message ?? "").replace(/^Value error, /, "");
      return name && name !== "body" ? `${name}: ${text}` : text;
    })
    .filter(Boolean);
  return messages.length ? messages.join("; ") : null;
}

export function getApiErrorMessage(error: unknown) {
  if (!axios.isAxiosError<ApiErrorBody>(error)) {
    return error instanceof Error ? error.message : "Something went wrong. Please try again.";
  }
  if (!error.response) {
    return error.code === "ECONNABORTED"
      ? "The server is taking too long to respond (it may be starting up). Please try again."
      : "Unable to reach the server. Check your connection and try again.";
  }

  const status = error.response.status;
  const body = error.response.data?.error;
  if (status === 422 && body?.code === "validation_error") {
    return validationDetails(body.details) ?? "Please check the highlighted values and try again.";
  }
  if (status === 503 && body?.message) return body.message;
  if (status >= 500) return "The server encountered an error. Please try again later.";
  if (body?.message) {
    const missing = (body.details as { missing?: string[] } | null)?.missing;
    return missing?.length ? `${body.message} Missing: ${missing.join(", ")}.` : body.message;
  }
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You do not have permission to perform this action.";
  if (status === 429) return "Too many attempts. Please wait a minute and try again.";
  return "The request could not be completed. Please try again.";
}
