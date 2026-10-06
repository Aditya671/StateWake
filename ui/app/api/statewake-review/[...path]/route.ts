import { NextRequest } from "next/server";
import {
  encodedReviewApiPath,
  isAllowedReviewApiPath,
} from "@/lib/api/review-proxy-policy";

const MAX_PROXY_BODY_BYTES = 16_384;

function configuredOrigin(): URL {
  const raw = process.env.STATEWAKE_REVIEW_API_ORIGIN ?? "http://127.0.0.1:8789";
  const origin = new URL(raw);
  if (
    !["http:", "https:"].includes(origin.protocol) ||
    origin.username ||
    origin.password ||
    origin.pathname !== "/" ||
    origin.search ||
    origin.hash
  ) {
    throw new Error(
      "STATEWAKE_REVIEW_API_ORIGIN must be an http(s) origin without embedded credentials",
    );
  }
  return origin;
}

function requiredSecret(name: "STATEWAKE_REVIEW_API_TOKEN" | "STATEWAKE_REVIEW_CSRF_TOKEN"): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is not configured`);
  return value;
}

function expectedBrowserOrigin(): string {
  const raw = process.env.STATEWAKE_UI_PUBLIC_ORIGIN?.trim();
  if (!raw) throw new Error("STATEWAKE_UI_PUBLIC_ORIGIN is not configured");
  const origin = new URL(raw);
  if (
    !["http:", "https:"].includes(origin.protocol) ||
    origin.username ||
    origin.password ||
    origin.pathname !== "/" ||
    origin.search ||
    origin.hash
  ) {
    throw new Error("STATEWAKE_UI_PUBLIC_ORIGIN must be an http(s) origin without credentials");
  }
  return origin.origin;
}

function invalidPath(): Response {
  return Response.json(
    {
      error: {
        code: "INVALID_REVIEW_PROXY_PATH",
        message: "unsupported StateWake review API request",
      },
    },
    { status: 400 },
  );
}

function reviewApiUnavailable(): Response {
  return Response.json(
    {
      error: {
        code: "REVIEW_API_UNAVAILABLE",
        message: "the configured StateWake review API is unavailable",
      },
    },
    { status: 503 },
  );
}

async function proxy(
  request: NextRequest,
  parts: string[],
  method: "GET" | "POST",
): Promise<Response> {
  if (!isAllowedReviewApiPath(parts) || request.nextUrl.search !== "") return invalidPath();
  if (method === "POST" && parts[2] === "review-capabilities") return invalidPath();

  let token: string;
  let csrf: string;
  try {
    token = requiredSecret("STATEWAKE_REVIEW_API_TOKEN");
    csrf = requiredSecret("STATEWAKE_REVIEW_CSRF_TOKEN");
  } catch {
    return reviewApiUnavailable();
  }

  let publicOrigin: string;
  try {
    publicOrigin = expectedBrowserOrigin();
  } catch {
    return reviewApiUnavailable();
  }

  let requestBody: ArrayBuffer | null = null;
  if (method === "POST") {
    const origin = request.headers.get("origin")?.replace(/\/$/, "") ?? "";
    if (origin !== publicOrigin) {
      return Response.json(
        {
          error: {
            code: "ORIGIN_DENIED",
            message: "review write origin is not allowed",
          },
        },
        { status: 403 },
      );
    }
    requestBody = await request.arrayBuffer();
    if (requestBody.byteLength > MAX_PROXY_BODY_BYTES) {
      return Response.json(
        {
          error: {
            code: "REVIEW_REQUEST_TOO_LARGE",
            message: "review request exceeds configured limits",
          },
        },
        { status: 413 },
      );
    }
  }

  const target = new URL(encodedReviewApiPath(parts), configuredOrigin());
  const headers = new Headers({
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
    "X-StateWake-CSRF": csrf,
  });
  const ifMatch = request.headers.get("if-match");
  const ifNoneMatch = request.headers.get("if-none-match");
  const idempotencyKey = request.headers.get("idempotency-key");
  if (ifMatch) headers.set("If-Match", ifMatch);
  if (ifNoneMatch) headers.set("If-None-Match", ifNoneMatch);
  if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);
  if (method === "POST") {
    headers.set("Content-Type", "application/json");
    headers.set("Origin", publicOrigin);
  }

  let response: Response;
  try {
    const init: RequestInit = {
      method,
      headers,
      cache: "no-store",
      signal: request.signal,
      redirect: "manual",
    };
    if (requestBody !== null) init.body = requestBody;
    response = await fetch(target, init);
  } catch {
    return reviewApiUnavailable();
  }

  const outbound = new Headers();
  for (const name of ["content-type", "etag", "cache-control"]) {
    const value = response.headers.get(name);
    if (value) outbound.set(name, value);
  }
  outbound.set("X-StateWake-Proxy", "review-boundary");
  if (response.status === 304) {
    return new Response(null, { status: 304, headers: outbound });
  }
  return new Response(await response.arrayBuffer(), {
    status: response.status,
    headers: outbound,
  });
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  return proxy(request, path, "GET");
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  return proxy(request, path, "POST");
}
