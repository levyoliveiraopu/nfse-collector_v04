"use client";

import * as React from "react";

import { ErrorBoundary } from "@/components/ui/error-boundary";

function Exploder({ attempt, armed }: { attempt: number; armed: boolean }) {
  if (!armed) {
    return <p className="text-sm text-muted-foreground">Preparando demonstração...</p>;
  }

  if (attempt === 0) {
    throw new Error("Falha simulada no primeiro render.");
  }
  return (
    <p className="text-sm text-muted-foreground">
      Render bem-sucedido no attempt #{attempt}.
    </p>
  );
}

export function ErrorBoundaryDemo() {
  const [attempt, setAttempt] = React.useState(0);
  const [nonce, setNonce] = React.useState(0);
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="space-y-3">
      <ErrorBoundary
        key={nonce}
        onRetry={() => {
          setAttempt((value) => value + 1);
          setNonce((value) => value + 1);
        }}
      >
        <Exploder attempt={attempt} armed={mounted} />
      </ErrorBoundary>
      <button
        type="button"
        onClick={() => {
          setAttempt(0);
          setNonce((value) => value + 1);
        }}
        className="inline-flex h-8 items-center rounded-md border border-border bg-background px-3 text-xs font-medium text-foreground shadow-sm hover:bg-accent"
      >
        Resetar demo (disparar erro de novo)
      </button>
    </div>
  );
}
