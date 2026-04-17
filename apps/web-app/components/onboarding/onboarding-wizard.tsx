"use client";

/**
 * Wizard de onboarding (APP-11) — 3 passos ate a 1a coleta.
 *
 * Regras de apresentacao:
 * - Montado em `app/dashboard/layout.tsx`: aparece em qualquer rota
 *   autenticada enquanto o onboarding estiver incompleto.
 * - Modal persistente: NAO pode ser fechado clicando fora. O unico
 *   caminho de saida sem concluir e o botao "Pular por enquanto" (skip
 *   destacado como nao recomendado, por DoD), que suprime o modal por
 *   24h via localStorage. Apos 24h reaparece.
 * - Progresso "salva": a detecao de passo e 100% derivada do backend
 *   (`use-onboarding-state`), entao fechar a aba e reabrir retoma no
 *   passo correto sem estado local.
 * - Fluxo feliz: passo 3 dispara `first_collection_done` no
 *   `/onboarding/first-collection-done` (outbox de email) e termina
 *   com uma tela de "parabens" + botao "Ir para o dashboard".
 */
import * as React from "react";
import { PartyPopper, X } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";

import { StepCredencial } from "./step-credencial";
import { StepEmpresa } from "./step-empresa";
import { StepExecucao } from "./step-execucao";
import {
  isDismissalActive,
  readDismissedAt,
  useOnboardingState,
  writeDismissedAt,
  clearDismissed,
} from "./use-onboarding-state";

export function OnboardingWizard() {
  const { user, status } = useAuth();
  const state = useOnboardingState();

  const [dismissedAt, setDismissedAt] = React.useState<number | null>(null);
  const [showCelebration, setShowCelebration] = React.useState(false);

  // Rehidrata o flag local ao autenticar.
  React.useEffect(() => {
    if (!user) {
      setDismissedAt(null);
      return;
    }
    setDismissedAt(readDismissedAt(user.tenantId, user.userId));
  }, [user]);

  // Nao renderiza durante SSR / loading / sem sessao.
  if (status !== "authenticated" || !user) return null;

  // Enquanto ainda nao sabemos o estado, nao mostra nada (evita flash).
  if (state.isLoading) return null;
  // Se houver erro de backend, preferimos nao bloquear o user — banner
  // no dashboard (proprio `/dashboard`) pode aparecer em follow-up.
  if (state.isError) return null;

  // Concluido: mostra modal de parabens uma unica vez por sessao e sai.
  if (state.isComplete) {
    if (!showCelebration) {
      // Quando o passo 3 flipa para done, o usuario ja viu o feedback
      // inline de "primeira coleta concluida". O wizard em si fecha.
      return null;
    }
    return (
      <OnboardingCelebration
        onClose={() => {
          setShowCelebration(false);
          clearDismissed(user.tenantId, user.userId);
        }}
      />
    );
  }

  // Usuario escolheu "pular por enquanto" nas ultimas 24h → nao bloqueia.
  if (isDismissalActive(dismissedAt)) return null;

  const handleSkip = () => {
    if (!user) return;
    const now = Date.now();
    writeDismissedAt(user.tenantId, user.userId, now);
    setDismissedAt(now);
  };

  const handleAdvance = () => {
    state.refresh();
  };

  const handleExecutionCompleted = () => {
    state.refresh();
    setShowCelebration(true);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-wizard-title"
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-foreground/50 p-4 backdrop-blur-sm sm:items-center"
      data-testid="onboarding-wizard"
    >
      <div className="relative w-full max-w-xl rounded-lg border border-border bg-background text-foreground shadow-xl">
        <header className="flex flex-col gap-1 border-b border-border px-6 py-5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Onboarding · Passo {state.stepNumber} de 3
          </p>
          <h2
            id="onboarding-wizard-title"
            className="text-lg font-semibold tracking-tight"
          >
            {state.currentStep === "empresa"
              ? "Cadastre sua primeira empresa"
              : state.currentStep === "credencial"
                ? "Envie o certificado digital A1"
                : "Rode a primeira coleta"}
          </h2>
          <StepsProgress stepNumber={state.stepNumber} />
        </header>

        <div className="px-6 py-5">
          {state.currentStep === "empresa" ? (
            <StepEmpresa onCreated={handleAdvance} />
          ) : null}
          {state.currentStep === "credencial" && state.firstCompany ? (
            <StepCredencial
              companyId={state.firstCompany.id}
              onUploaded={handleAdvance}
            />
          ) : null}
          {state.currentStep === "execucao" && state.firstCompany ? (
            <StepExecucao
              company={state.firstCompany}
              onCompleted={handleExecutionCompleted}
            />
          ) : null}
        </div>

        <footer className="flex flex-col gap-1 border-t border-border px-6 py-4">
          <button
            type="button"
            onClick={handleSkip}
            className="self-start text-xs text-muted-foreground underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            data-testid="onboarding-skip"
          >
            Pular por enquanto
          </button>
          <p className="text-[11px] text-muted-foreground/80">
            Nao recomendado: sem credencial a coleta nao pode iniciar. Voce
            pode retomar aqui assim que voltar ao dashboard.
          </p>
        </footer>
      </div>
    </div>
  );
}

function StepsProgress({
  stepNumber,
}: {
  stepNumber: 1 | 2 | 3 | 4;
}) {
  return (
    <ol
      aria-label="Passos do onboarding"
      className="mt-2 flex gap-2 text-xs"
      data-testid="onboarding-steps"
    >
      {[1, 2, 3].map((n) => {
        const active = stepNumber === n;
        const done = stepNumber > n;
        return (
          <li
            key={n}
            className={
              "flex items-center gap-1 rounded-full border px-2.5 py-0.5 " +
              (active
                ? "border-primary bg-primary text-primary-foreground"
                : done
                  ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-700 dark:text-emerald-400"
                  : "border-border text-muted-foreground")
            }
            aria-current={active ? "step" : undefined}
          >
            <span className="font-mono text-[10px]">{n}</span>
            <span>
              {n === 1 ? "Empresa" : n === 2 ? "Credencial" : "Coleta"}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function OnboardingCelebration({ onClose }: { onClose: () => void }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-celebration-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/50 p-4 backdrop-blur-sm"
      data-testid="onboarding-celebration"
    >
      <div className="relative w-full max-w-md rounded-lg border border-border bg-background p-6 shadow-xl">
        <button
          type="button"
          onClick={onClose}
          aria-label="Fechar"
          className="absolute right-3 top-3 inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
        <div className="flex flex-col items-center gap-3 text-center">
          <PartyPopper
            className="h-10 w-10 text-emerald-500"
            aria-hidden="true"
          />
          <h3
            id="onboarding-celebration-title"
            className="text-lg font-semibold"
          >
            Onboarding concluido!
          </h3>
          <p className="text-sm text-muted-foreground">
            Sua primeira coleta foi registrada e um email de confirmacao sera
            enviado. A partir daqui o dashboard acompanha tudo em tempo real.
          </p>
          <button
            type="button"
            onClick={onClose}
            className="mt-2 inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Ir para o dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
