import axios from "axios";

type ApiErrorBody = { message?: unknown };

export function getApiErrorStatus(error: unknown) {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

export function getApiErrorMessage(error: unknown) {
  if (!axios.isAxiosError<ApiErrorBody>(error)) {
    return error instanceof Error ? error.message : "Something went wrong. Please try again.";
  }

  const status = error.response?.status;
  if (status === 500 || (status !== undefined && status >= 500)) {
    return "The server encountered an error. Please try again later.";
  }

  const message = error.response?.data?.message;
  if (typeof message === "string" && message.trim()) {
    return message;
  }

  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You do not have permission to perform this action.";
  if (status === 400) return "Please check your information and try again.";
  if (!error.response)
    return "Unable to connect to CampusConnect. Check your connection and try again.";
  return "The request could not be completed. Please try again.";
}
