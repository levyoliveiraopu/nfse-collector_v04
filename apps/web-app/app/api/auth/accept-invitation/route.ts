import { NextResponse } from "next/server";
import {
  buildSessionResponse,
  proxyToApi,
} from "@/lib/auth/server";
import type { AuthTokenResponse } from "@/lib/auth/types";

export const runtime = "nodejs";

/**
 * Aceita um convite pendente e inicia sessao (APP-09).
 *
 * Proxy fino para `POST /tenant/invitations/accept` da API FastAPI.
 * O endpoint backend — a ser entregue em ticket API futuro — espera:
 *
 *   { "token": "<convite>", "name": "...", "password": "..." }
 *
 * e responde com o mesmo shape `AuthTokenResponse` do login: a partir
 * dai o refresh token vai para o cookie httpOnly, o access volta no body.
 */
export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object") {
    return NextResponse.json(
      { detail: "payload invalido" },
      { status: 400 },
    );
  }

  const upstream = await proxyToApi("/tenant/invitations/accept", body);
  const text = await upstream.text();
  if (!upstream.ok) {
    return new NextResponse(text, {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") ?? "application/json",
      },
    });
  }
  const raw = JSON.parse(text) as AuthTokenResponse;
  return buildSessionResponse(raw);
}
