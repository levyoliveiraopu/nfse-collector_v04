"use client";

/**
 * Deriva o estado do wizard de onboarding (APP-11) a partir do backend.
 *
 * A unica verdade consultada sao os endpoints ja existentes:
 * - `listCompanies`: quantas empresas o tenant ja tem?
 * - `fetchCredential`: a 1a empresa ja tem credencial ativa (nao
 *   `expired`/`revoked`/`invalid`)?
 * - `listExecutions`: ja houve execucao `succeeded` ou `partial`?
 *
 * Decisao explicita: derivar do backend em vez de guardar um flag em
 * `users`/`tenants` evita uma migration nova. O "se fechar retoma" da
 * DoD cai naturalmente — tudo e recomputado no mount.
 *
 * O unico estado local do navegador e `dismissedAt` (timestamp em
 * localStorage por `${tenantId}:${userId}`), consumido pela UI para
 * suprimir o modal por 24h quando o usuario clica em "Pular por
 * enquanto". O banner do dashboard sempre oferece "Retomar".
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/components/auth/auth-provider";
import { listCompanies, type Company } from "@/lib/api/companies";
import {
  fetchCredential,
  type Credential,
  type CredentialStatus,
} from "@/lib/companies/credentials";
import { listExecutions } from "@/lib/api/executions";

export type OnboardingStep = "empresa" | "credencial" | "execucao" | "done";

export interface OnboardingState {
  /** `true` quando os 3 passos ja foram cumpridos. */
  isComplete: boolean;
  /** Passo atual — `"done"` quando `isComplete`. */
  currentStep: OnboardingStep;
  /** Numero do passo (1..3) ou 4 quando finalizado. Para UI. */
  stepNumber: 1 | 2 | 3 | 4;
  /** 1a empresa do tenant (quando ja existe). */
  firstCompany: Company | null;
  /** Credencial da 1a empresa (quando ja configurada). */
  credential: Credential | null;
  /** Carregando dados do backend. */
  isLoading: boolean;
  /** Algum dos `useQuery` falhou — UI mostra fallback. */
  isError: boolean;
  /** Forca refetch (apos avancar de passo). */
  refresh: () => void;
}

const ACTIVE_CREDENTIAL_STATUSES: readonly CredentialStatus[] = ["active"];

function isCredentialActive(cred: Credential | null): boolean {
  if (!cred) return false;
  if (!ACTIVE_CREDENTIAL_STATUSES.includes(cred.status)) return false;
  if (cred.cert_not_after) {
    const notAfter = new Date(cred.cert_not_after).getTime();
    if (!Number.isNaN(notAfter) && notAfter <= Date.now()) return false;
  }
  return true;
}

export function useOnboardingState(): OnboardingState {
  const { accessToken, refresh: refreshAuth, status } = useAuth();

  const ctx = React.useMemo(
    () => ({
      accessToken,
      onTokenRefreshed: () => {
        void refreshAuth();
      },
    }),
    [accessToken, refreshAuth],
  );

  const enabled = status === "authenticated" && Boolean(accessToken);

  const companiesQuery = useQuery({
    queryKey: ["onboarding", "companies"],
    queryFn: () =>
      listCompanies(
        { pagination: { pageIndex: 0, pageSize: 1 }, sort: null, filters: {} },
        ctx,
      ),
    enabled,
    staleTime: 10_000,
  });

  const firstCompany = companiesQuery.data?.rows[0] ?? null;

  const credentialQuery = useQuery({
    queryKey: ["onboarding", "credential", firstCompany?.id],
    queryFn: () =>
      firstCompany
        ? fetchCredential(firstCompany.id, ctx)
        : Promise.resolve(null),
    enabled: enabled && Boolean(firstCompany),
    staleTime: 10_000,
  });

  const credential = credentialQuery.data ?? null;

  // Duas queries paralelas para cobrir succeeded OU partial: se qualquer
  // uma tiver total > 0, o passo 3 ja foi cumprido.
  const succeededQuery = useQuery({
    queryKey: ["onboarding", "executions", "succeeded"],
    queryFn: () =>
      listExecutions({ page: 1, page_size: 1, status: "succeeded" }, ctx),
    enabled,
    staleTime: 10_000,
  });
  const partialQuery = useQuery({
    queryKey: ["onboarding", "executions", "partial"],
    queryFn: () =>
      listExecutions({ page: 1, page_size: 1, status: "partial" }, ctx),
    enabled,
    staleTime: 10_000,
  });

  const hasSuccessfulExecution =
    (succeededQuery.data?.total ?? 0) > 0 ||
    (partialQuery.data?.total ?? 0) > 0;

  const isLoading =
    companiesQuery.isLoading ||
    (Boolean(firstCompany) && credentialQuery.isLoading) ||
    succeededQuery.isLoading ||
    partialQuery.isLoading;

  const isError =
    companiesQuery.isError ||
    credentialQuery.isError ||
    succeededQuery.isError ||
    partialQuery.isError;

  const hasCompany = Boolean(firstCompany);
  const hasActiveCredential = isCredentialActive(credential);

  let currentStep: OnboardingStep;
  let stepNumber: 1 | 2 | 3 | 4;
  if (!hasCompany) {
    currentStep = "empresa";
    stepNumber = 1;
  } else if (!hasActiveCredential) {
    currentStep = "credencial";
    stepNumber = 2;
  } else if (!hasSuccessfulExecution) {
    currentStep = "execucao";
    stepNumber = 3;
  } else {
    currentStep = "done";
    stepNumber = 4;
  }

  const refresh = React.useCallback(() => {
    void companiesQuery.refetch();
    void credentialQuery.refetch();
    void succeededQuery.refetch();
    void partialQuery.refetch();
  }, [companiesQuery, credentialQuery, succeededQuery, partialQuery]);

  return {
    isComplete: currentStep === "done",
    currentStep,
    stepNumber,
    firstCompany,
    credential,
    isLoading,
    isError,
    refresh,
  };
}

/* ------------------------------- Dismiss ------------------------------- */

const DISMISS_KEY_PREFIX = "nfse:onboarding:dismissed:";
const DISMISS_TTL_MS = 24 * 60 * 60 * 1000;

export function buildDismissKey(tenantId: string, userId: string): string {
  return `${DISMISS_KEY_PREFIX}${tenantId}:${userId}`;
}

export function readDismissedAt(
  tenantId: string,
  userId: string,
  storage: Storage = typeof window !== "undefined" ? window.localStorage : undefinedStorage(),
): number | null {
  try {
    const raw = storage.getItem(buildDismissKey(tenantId, userId));
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

export function writeDismissedAt(
  tenantId: string,
  userId: string,
  at: number = Date.now(),
  storage: Storage = typeof window !== "undefined" ? window.localStorage : undefinedStorage(),
): void {
  try {
    storage.setItem(buildDismissKey(tenantId, userId), String(at));
  } catch {
    // localStorage indisponivel (ex.: modo privado antigo). No-op — o
    // wizard reaparece na proxima sessao, e nao corrompe o fluxo.
  }
}

export function clearDismissed(
  tenantId: string,
  userId: string,
  storage: Storage = typeof window !== "undefined" ? window.localStorage : undefinedStorage(),
): void {
  try {
    storage.removeItem(buildDismissKey(tenantId, userId));
  } catch {
    // no-op
  }
}

export function isDismissalActive(
  dismissedAt: number | null,
  now: number = Date.now(),
): boolean {
  if (dismissedAt === null) return false;
  return now - dismissedAt < DISMISS_TTL_MS;
}

// Stub para SSR / ambiente sem localStorage — nunca chamado em runtime
// real, mas mantem a assinatura sincrona das funcoes.
function undefinedStorage(): Storage {
  const noop: Storage = {
    get length() {
      return 0;
    },
    clear: () => undefined,
    getItem: () => null,
    key: () => null,
    removeItem: () => undefined,
    setItem: () => undefined,
  };
  return noop;
}
