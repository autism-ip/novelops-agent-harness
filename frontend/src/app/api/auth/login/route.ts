/**
 * [INPUT]: 依赖环境变量 AUTH_PASSWORD，消费 @/lib/session 的 signToken
 * [OUTPUT]: POST /api/auth/login — 签发 session_token cookie
 * [POS]: api/auth/login 的登录端点，被浏览器端 client.ts 消费
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

import { type NextRequest, NextResponse } from "next/server";
import { signToken } from "@/lib/session";

const AUTH_PW = process.env.AUTH_PASSWORD || "";

export async function POST(request: NextRequest) {
  if (!AUTH_PW) {
    return NextResponse.json(
      { detail: "Server configuration error" },
      { status: 503 }
    );
  }

  let body: { password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { detail: "Invalid request body" },
      { status: 400 }
    );
  }

  if (body.password !== AUTH_PW) {
    return NextResponse.json(
      { detail: "Invalid credentials" },
      { status: 401 }
    );
  }

  const token = await signToken("authenticated");

  const response = NextResponse.json({ detail: "Login successful" });
  response.cookies.set("session_token", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24, // 24 hours
  });

  return response;
}
