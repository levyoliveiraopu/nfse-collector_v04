import { NextResponse } from "next/server";
import {
  buildSessionResponse,
  clearRefreshCookie,
  proxyToApi,
  readRefreshCookie,
} from "@/lib/auth/server";
import type { AuthTokenResponse } from "@/lib/auth/types";

export const runtime = "nodejs";

/**
 * Troca o refresh httpOnly por um novo par access+refresh. O cliente nunca
 * enxerga o refresh; apenas recebe o novo access + metadados de sessao.
 */
export async function POST() {
  const refresh = readRefreshCookie();
  if (!refresh) {
    return NextResponse.json(
      { detail: "sessao expirada" },
      { status: 401 },
    );
  }

  const upstream = await proxyToApi("/auth/refresh", {
    refresh_token: refresh,
  });

  if (!upstream.ok) {
    // Refresh rejeitado pela API -> limpa cookie para forcar re-login.
    const res = NextResponse.json(
      { detail: "sessao expirada" },
      { status: 401 },
    );
    return clearRefreshCookie(res);
  }

  const raw = (await upstream.json()) as AuthTokenResponse;
  return buildSessionResponse(raw);
}
