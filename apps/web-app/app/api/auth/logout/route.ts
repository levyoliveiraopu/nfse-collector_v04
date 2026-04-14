import { NextResponse } from "next/server";
import {
  clearRefreshCookie,
  proxyToApi,
  readRefreshCookie,
} from "@/lib/auth/server";

export const runtime = "nodejs";

/**
 * Revoga o refresh atual na API (best-effort) e limpa o cookie httpOnly.
 * Sempre 200 para nao vazar estado de sessao.
 */
export async function POST() {
  const refresh = readRefreshCookie();
  if (refresh) {
    try {
      await proxyToApi("/auth/logout", { refresh_token: refresh });
    } catch {
      // best-effort; nao propagar falha de rede para o logout local.
    }
  }
  const res = NextResponse.json({ ok: true });
  return clearRefreshCookie(res);
}
