/**
 * Cliente HTTP de `/onboarding/*` (consome APP-11 server side).
 *
 * O wizard chama `postFirstCollectionDone` quando detecta a primeira
 * execucao `succeeded`/`partial`. O backend e idempotente: chamadas
 * subsequentes retornam `already_recorded=true`.
 */
import { ApiError, apiFetch } from "@/lib/auth/api-client";

import type { ApiCallContext } from "./companies";

export interface FirstCollectionDoneResponse {
  already_recorded: boolean;
  notification_id: string | null;
}

export async function postFirstCollectionDone(
  ctx: ApiCallContext,
): Promise<FirstCollectionDoneResponse> {
  const res = await apiFetch(`/onboarding/first-collection-done`, {
    method: "POST",
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    signal: ctx.signal,
  });
  const text = await res.text();
  if (!res.ok) {
    let detail: unknown = text;
    try {
      detail = text ? JSON.parse(text) : null;
    } catch {
      // mantem string crua
    }
    throw new ApiError(res.status, detail);
  }
  return JSON.parse(text) as FirstCollectionDoneResponse;
}
