/**
 * [INPUT]: 依赖环境变量 BACKEND_API_URL, BACKEND_API_KEY, SESSION_SECRET（服务端专用）
 * [OUTPUT]: Next.js catch-all API route handler，代理所有 /api/* 请求到后端
 * [POS]: app/api/[...path] 的服务端代理层，验证签名 session 后注入 x-api-key
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

import { type NextRequest, NextResponse } from "next/server";
import { verifyToken } from "@/lib/session";

const BACKEND_URL = process.env.BACKEND_API_URL || "http://localhost:8000";
const BACKEND_KEY = process.env.BACKEND_API_KEY || "";

// Paths that the backend exposes without x-api-key
const PUBLIC_BACKEND_PATHS = new Set(["system/health", "system/status"]);

async function proxyRequest(
  request: NextRequest,
  params: Promise<{ path: string[] }>
): Promise<NextResponse> {
  const { path } = await params;
  const targetPath = path.join("/");

  const isPublic = PUBLIC_BACKEND_PATHS.has(targetPath);

  // Protected routes require a valid signed session cookie
  if (!isPublic) {
    const token = request.cookies.get("session_token")?.value;
    if (!token) {
      return NextResponse.json(
        { detail: "Authentication required" },
        { status: 401 }
      );
    }
    let valid: string | null;
    try {
      valid = await verifyToken(token);
    } catch {
      return NextResponse.json(
        { detail: "Server configuration error" },
        { status: 503 }
      );
    }
    if (!valid) {
      return NextResponse.json(
        { detail: "Authentication required" },
        { status: 401 }
      );
    }
  }

  const targetUrl = new URL(`/api/${targetPath}`, BACKEND_URL);
  targetUrl.search = request.nextUrl.search;

  const headers = new Headers();
  headers.set(
    "Content-Type",
    request.headers.get("Content-Type") || "application/json"
  );

  // Only inject backend key for protected routes
  if (!isPublic) {
    if (!BACKEND_KEY) {
      return NextResponse.json(
        { detail: "Server configuration error" },
        { status: 503 }
      );
    }
    headers.set("x-api-key", BACKEND_KEY);
  }

  const init: RequestInit = {
    method: request.method,
    headers,
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  const res = await fetch(targetUrl.toString(), init);
  const body = await res.text();

  return new NextResponse(body, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("Content-Type") || "application/json",
    },
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, params);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, params);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, params);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, params);
}
