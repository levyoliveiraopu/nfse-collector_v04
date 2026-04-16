/**
 * Cliente HTTP para gestao de usuarios do tenant (APP-09).
 *
 * Endpoints consumidos (a serem entregues em ticket API futuro — seguindo
 * o padrao da APP-01 com o fluxo de recuperacao de senha):
 *
 *   GET    /tenant/members
 *   PATCH  /tenant/members/{user_id}        (body: { role })
 *   DELETE /tenant/members/{user_id}
 *   GET    /tenant/invitations
 *   POST   /tenant/invitations              (body: { email, role })
 *   POST   /tenant/invitations/{id}/revoke
 *   POST   /tenant/invitations/accept       (body: { token, name, password })
 *
 * As chamadas autenticadas usam o `apiFetch` do APP-01 — access token
 * injetado via Authorization, refresh automatico em 401.
 */
import { ApiError, apiFetch } from "@/lib/auth/api-client";
import type { AuthSessionPayload } from "@/lib/auth/types";
import type { Invitation, Member, Role } from "./types";

type AuthContext = {
  accessToken: string | null;
  onTokenRefreshed?: (payload: AuthSessionPayload) => void;
};

async function parseJsonSafe(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function readOrThrow<T>(res: Response): Promise<T> {
  const payload = await parseJsonSafe(res);
  if (!res.ok) {
    throw new ApiError(res.status, payload);
  }
  return payload as T;
}

/** GET /tenant/members */
export async function listMembers(ctx: AuthContext): Promise<Member[]> {
  const res = await apiFetch("/tenant/members", {
    method: "GET",
    ...ctx,
  });
  return readOrThrow<Member[]>(res);
}

/** GET /tenant/invitations */
export async function listInvitations(ctx: AuthContext): Promise<Invitation[]> {
  const res = await apiFetch("/tenant/invitations", {
    method: "GET",
    ...ctx,
  });
  return readOrThrow<Invitation[]>(res);
}

/** POST /tenant/invitations */
export async function inviteMember(
  ctx: AuthContext,
  body: { email: string; role: Role },
): Promise<Invitation> {
  const res = await apiFetch("/tenant/invitations", {
    method: "POST",
    body: JSON.stringify(body),
    ...ctx,
  });
  return readOrThrow<Invitation>(res);
}

/** POST /tenant/invitations/{id}/revoke */
export async function revokeInvitation(
  ctx: AuthContext,
  invitationId: string,
): Promise<void> {
  const res = await apiFetch(
    `/tenant/invitations/${encodeURIComponent(invitationId)}/revoke`,
    { method: "POST", ...ctx },
  );
  if (!res.ok) {
    const payload = await parseJsonSafe(res);
    throw new ApiError(res.status, payload);
  }
}

/** PATCH /tenant/members/{user_id} */
export async function updateMemberRole(
  ctx: AuthContext,
  userId: string,
  role: Role,
): Promise<Member> {
  const res = await apiFetch(
    `/tenant/members/${encodeURIComponent(userId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ role }),
      ...ctx,
    },
  );
  return readOrThrow<Member>(res);
}

/** DELETE /tenant/members/{user_id} */
export async function removeMember(
  ctx: AuthContext,
  userId: string,
): Promise<void> {
  const res = await apiFetch(
    `/tenant/members/${encodeURIComponent(userId)}`,
    { method: "DELETE", ...ctx },
  );
  if (!res.ok) {
    const payload = await parseJsonSafe(res);
    throw new ApiError(res.status, payload);
  }
}

/**
 * POST /tenant/invitations/accept — chamado sem sessao autenticada (o
 * token do convite e o credential). Fluxo: user abre /aceitar-convite/[token],
 * envia nome+senha, e recebe uma `AuthSessionPayload` de sessao iniciada.
 */
export async function acceptInvitation(body: {
  token: string;
  name: string;
  password: string;
}): Promise<AuthSessionPayload> {
  const res = await fetch("/api/auth/accept-invitation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await parseJsonSafe(res);
  if (!res.ok) {
    throw new ApiError(res.status, payload);
  }
  return payload as AuthSessionPayload;
}

export { ApiError };
