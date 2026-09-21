import { NextRequest, NextResponse } from "next/server";

const ALLOWED_ROOTS = new Set(["_allauth", "api", "billing", "usage-logs"]);
const SAFE_RESPONSE_HEADERS = ["content-type", "cache-control", "content-disposition", "location"];

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (!path.length || !ALLOWED_ROOTS.has(path[0]) || path.some((segment) => segment === "..")) {
    return NextResponse.json({ error: "Unsupported backend route." }, { status: 404 });
  }

  const base = process.env.DJANGO_INTERNAL_URL ?? "http://127.0.0.1:8000";
  const upstream = new URL(`/${path.map(encodeURIComponent).join("/")}`, base);
  if (path[0] !== "_allauth" && !upstream.pathname.endsWith("/")) {
    upstream.pathname += "/";
  }
  request.nextUrl.searchParams.forEach((value, key) => {
    if (key !== "_redirect") upstream.searchParams.append(key, value);
  });

  const headers = new Headers();
  for (const name of ["accept", "content-type", "cookie", "x-csrftoken", "x-requested-with"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("x-forwarded-proto", request.nextUrl.protocol.replace(":", ""));

  const method = request.method.toUpperCase();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30_000);
  try {
    const response = await fetch(upstream, {
      method,
      headers,
      body: ["GET", "HEAD"].includes(method) ? undefined : await request.arrayBuffer(),
      redirect: "manual",
      cache: "no-store",
      signal: controller.signal,
    });

    const location = response.headers.get("location");
    if (request.nextUrl.searchParams.get("_redirect") === "manual" && location && response.status >= 300 && response.status < 400) {
      return NextResponse.json({ redirect: location });
    }

    const outputHeaders = new Headers();
    for (const name of SAFE_RESPONSE_HEADERS) {
      const value = response.headers.get(name);
      if (value) outputHeaders.set(name, value);
    }
    for (const cookie of response.headers.getSetCookie()) outputHeaders.append("set-cookie", cookie);
    return new NextResponse(response.body, { status: response.status, headers: outputHeaders });
  } catch (error) {
    const message = error instanceof Error && error.name === "AbortError"
      ? "The backend timed out."
      : "The backend is unavailable.";
    return NextResponse.json({ error: message }, { status: 502 });
  } finally {
    clearTimeout(timeout);
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
