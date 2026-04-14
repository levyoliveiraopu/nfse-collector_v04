import { NextResponse } from "next/server";
import {
  buildSessionResponse,
  proxyToApi,
} from "@/lib/auth/server";
import type { AuthTokenResponse } from "@/lib/auth/types";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object") {
    return NextResponse.json(
      { detail: "payload invalido" },
      { status: 400 },
    );
  }

  const upstream = await proxyToApi("/auth/login", body);
  const text = await upstream.text();
  if (!upstream.ok) {
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  }
  const raw = JSON.parse(text) as AuthTokenResponse;
  return buildSessionResponse(raw);
}
