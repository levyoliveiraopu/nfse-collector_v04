import { ApiError, apiFetch } from "@/lib/auth/api-client";
import type { AuthSessionPayload } from "@/lib/auth/types";
import type { HelpRouteKey } from "@/lib/help/catalog";

export type HelpEventType =
  | "article_opened"
  | "search_performed"
  | "search_no_results"
  | "tour_started"
  | "tour_completed"
  | "tour_skipped"
  | "tour_failed"
  | "feedback_yes"
  | "feedback_no";

export type HelpEvent = {
  event_type: HelpEventType;
  article_slug?: string;
  route_key?: HelpRouteKey;
  tour_id?: string;
};

export type HelpApiContext = {
  accessToken?: string | null;
  onTokenRefreshed?: (payload: AuthSessionPayload) => void;
};

export type HelpInsightCounts = Record<HelpEventType, number>;

export type HelpInsightRow = HelpInsightCounts & {
  article_slug: string;
  route_key: string;
};

export type HelpInsights = {
  days: 7 | 30 | 90;
  date_from: string;
  date_to: string;
  totals: HelpInsightCounts;
  rows: HelpInsightRow[];
};

async function parseError(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function recordHelpEvent(
  ctx: HelpApiContext,
  event: HelpEvent,
): Promise<void> {
  const response = await apiFetch("/help/events", {
    method: "POST",
    body: JSON.stringify(event),
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
    keepalive: true,
  });
  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response));
  }
}

export async function getHelpInsights(
  ctx: HelpApiContext,
  days: 7 | 30 | 90,
): Promise<HelpInsights> {
  const response = await apiFetch(`/help/insights?days=${days}`, {
    accessToken: ctx.accessToken,
    onTokenRefreshed: ctx.onTokenRefreshed,
  });
  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response));
  }
  return (await response.json()) as HelpInsights;
}
