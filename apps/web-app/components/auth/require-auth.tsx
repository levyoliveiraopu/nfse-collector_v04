"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth-provider";

/**
 * Guard client-side: redireciona para `/login` se a sessao for resolvida
 * como nao autenticada. Enquanto o AuthProvider esta `loading`, mostra
 * fallback (evita flash de conteudo protegido).
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status !== "authenticated") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex min-h-screen items-center justify-center text-sm text-muted-foreground"
      >
        Carregando sessao...
      </div>
    );
  }

  return <>{children}</>;
}
