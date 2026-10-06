import { NextRequest } from "next/server";
import {
  encodedReadApiPath,
  isAllowedReadApiPath,
  isAllowedReadApiQuery,
} from "@/lib/api/proxy-policy";

function configuredOrigin(): URL {
  const raw = process.env.STATEWAKE_READ_API_ORIGIN ?? "http://127.0.0.1:8788";
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
      "STATEWAKE_READ_API_ORIGIN must be an http(s) origin without embedded credentials",
    );
  }
  return origin;
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  if (
    !isAllowedReadApiPath(path) ||
    !isAllowedReadApiQuery(path, request.nextUrl.searchParams)
  ) {
    return Response.json(
      {
        error: {
          code: "INVALID_PROXY_PATH",
          message: "unsupported StateWake read API request",
        },
      },
      { status: 400 },
    );
  }

  const target = new URL(encodedReadApiPath(path), configuredOrigin());
  for (const [key, value] of request.nextUrl.searchParams.entries()) {
    target.searchParams.append(key, value);
  }
  const headers = new Headers({
    Accept: request.headers.get("accept") ?? "application/json",
  });
  const etag = request.headers.get("if-none-match");
  if (etag) headers.set("If-None-Match", etag);

  let response: Response;
  try {
    response = await fetch(target, {
      method: "GET",
      headers,
      cache: "no-store",
      signal: request.signal,
      redirect: "manual",
    });
  } catch {
    return Response.json(
      {
        error: {
          code: "READ_API_UNAVAILABLE",
          message: "the configured StateWake read API is unavailable",
        },
      },
      { status: 503 },
    );
  }

  const outbound = new Headers();
  for (const name of ["content-type", "etag", "cache-control"]) {
    const value = response.headers.get(name);
    if (value) outbound.set(name, value);
  }
  outbound.set("X-StateWake-Proxy", "read-only");
  if (response.status === 304) {
    return new Response(null, { status: 304, headers: outbound });
  }
  return new Response(await response.arrayBuffer(), {
    status: response.status,
    headers: outbound,
  });
}
