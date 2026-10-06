import axios from "axios";
import type { ApiErrorEnvelope } from "./dto";

export type ApiErrorCategory =
  | "unauthenticated"
  | "forbidden"
  | "not-found"
  | "conflict"
  | "invalid-request"
  | "rate-limited"
  | "unavailable"
  | "timeout"
  | "network"
  | "server"
  | "unexpected";

export class StateWakeApiError extends Error {
  constructor(
    message: string,
    public readonly category: ApiErrorCategory,
    public readonly code: string,
    public readonly status: number | null,
    public readonly retryable: boolean,
  ) {
    super(message);
    this.name = "StateWakeApiError";
  }
}

function categoryFor(status: number | undefined): ApiErrorCategory {
  if (status === 401) return "unauthenticated";
  if (status === 403) return "forbidden";
  if (status === 404) return "not-found";
  if (status === 409) return "conflict";
  if (status === 400 || status === 413 || status === 422) return "invalid-request";
  if (status === 429) return "rate-limited";
  if (status === 503) return "unavailable";
  if (status !== undefined && status >= 500) return "server";
  return "unexpected";
}

export function normalizeApiError(error: unknown): StateWakeApiError {
  if (!axios.isAxiosError<ApiErrorEnvelope>(error)) {
    return new StateWakeApiError(
      error instanceof Error ? error.message : "Unexpected UI error",
      "unexpected",
      "CLIENT_ERROR",
      null,
      false,
    );
  }
  if (error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") {
    return new StateWakeApiError("The StateWake read request timed out", "timeout", "TIMEOUT", null, true);
  }
  if (error.response === undefined) {
    return new StateWakeApiError("The StateWake read API could not be reached", "network", "NETWORK_ERROR", null, true);
  }

  const status = error.response.status;
  const payload = error.response.data;
  const code = typeof payload?.error?.code === "string" ? payload.error.code : "TRANSPORT_ERROR";
  const message = typeof payload?.error?.message === "string" ? payload.error.message : error.message;
  const category = categoryFor(status);
  return new StateWakeApiError(message, category, code, status, category === "unavailable" || category === "server" || category === "rate-limited");
}
