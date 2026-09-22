export type AuthUser = {
  id?: number | string;
  username: string;
  email: string;
  display?: string;
  first_name?: string;
  last_name?: string;
  has_usable_password?: boolean;
};

export type AuthResponse = {
  data?: {
    user?: AuthUser | null;
    [key: string]: unknown;
  };
  meta?: {
    is_authenticated?: boolean;
    [key: string]: unknown;
  };
  errors?: unknown;
  [key: string]: unknown;
};

type BackendOptions = RequestInit & {
  headers?: HeadersInit;
};

type ApiErrorPayload = {
  detail?: string;
  error?: string;
  message?: string;
  errors?: unknown;
  [key: string]: unknown;
};

export class BackendError extends Error {
  status: number;
  payload: ApiErrorPayload | null;

  constructor(
    message: string,
    status = 500,
    payload: ApiErrorPayload | null = null,
  ) {
    super(message);
    this.name = "BackendError";
    this.status = status;
    this.payload = payload;
  }
}

function getCookie(name: string): string {
  if (typeof document === "undefined") return "";

  const cookie = document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${name}=`));

  if (!cookie) return "";

  return decodeURIComponent(cookie.substring(name.length + 1));
}

export function csrfToken(): string {
  return getCookie("csrftoken");
}

function backendPath(path: string): string {
  const cleanPath = path.replace(/^\/+/, "");
  return `/api/backend/${cleanPath}`;
}

function isJsonResponse(response: Response): boolean {
  const contentType = response.headers.get("content-type") ?? "";
  return contentType.includes("application/json");
}

async function parseResponse(response: Response): Promise<unknown> {
  if (response.status === 204) return null;

  if (isJsonResponse(response)) {
    return response.json();
  }

  return response.text();
}

function isBodyPresent(method: string): boolean {
  return !["GET", "HEAD"].includes(method);
}

export async function backend<T = unknown>(
  path: string,
  options: BackendOptions = {},
): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);

  headers.set("Accept", "application/json");

  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (isBodyPresent(method)) {
    const token = csrfToken();

    if (token && !headers.has("X-CSRFToken")) {
      headers.set("X-CSRFToken", token);
    }

    if (!headers.has("X-Requested-With")) {
      headers.set("X-Requested-With", "XMLHttpRequest");
    }
  }

  const response = await fetch(backendPath(path), {
    ...options,
    method,
    headers,
    credentials: "include",
    cache: "no-store",
  });

  const payload = await parseResponse(response);

  if (!response.ok) {
    const data =
      payload && typeof payload === "object"
        ? (payload as ApiErrorPayload)
        : null;

    throw new BackendError(
      getPayloadMessage(data) ||
        `Request failed with status ${response.status}.`,
      response.status,
      data,
    );
  }

  return payload as T;
}

export async function session(): Promise<AuthResponse> {
  return backend<AuthResponse>("/_allauth/browser/v1/auth/session");
}

function getPayloadMessage(payload: ApiErrorPayload | null): string {
  if (!payload) return "";

  if (typeof payload.detail === "string") {
    return payload.detail;
  }

  if (typeof payload.error === "string") {
    return payload.error;
  }

  if (typeof payload.message === "string") {
    return payload.message;
  }

  if (typeof payload.errors === "string") {
    return payload.errors;
  }

  if (payload.errors && typeof payload.errors === "object") {
    const messages: string[] = [];

    for (const [field, value] of Object.entries(
      payload.errors as Record<string, unknown>,
    )) {
      if (Array.isArray(value)) {
        messages.push(`${field}: ${value.join(", ")}`);
      } else if (typeof value === "string") {
        messages.push(`${field}: ${value}`);
      } else if (value && typeof value === "object") {
        messages.push(`${field}: ${JSON.stringify(value)}`);
      }
    }

    if (messages.length) {
      return messages.join(" ");
    }
  }

  const fieldMessages: string[] = [];

  for (const [field, value] of Object.entries(payload)) {
    if (["detail", "error", "message", "errors"].includes(field)) {
      continue;
    }

    if (Array.isArray(value)) {
      fieldMessages.push(`${field}: ${value.join(", ")}`);
    } else if (typeof value === "string") {
      fieldMessages.push(`${field}: ${value}`);
    }
  }

  return fieldMessages.join(" ");
}

export function errorMessage(reason: unknown): string {
  if (reason instanceof BackendError) {
    return (
      getPayloadMessage(reason.payload) ||
      reason.message ||
      "Something went wrong. Please try again."
    );
  }

  if (reason instanceof Error) {
    return reason.message || "Something went wrong. Please try again.";
  }

  if (typeof reason === "string") {
    return reason;
  }

  if (reason && typeof reason === "object") {
    const payload = reason as ApiErrorPayload;

    return (
      getPayloadMessage(payload) ||
      "Something went wrong. Please try again."
    );
  }

  return "Something went wrong. Please try again.";
}