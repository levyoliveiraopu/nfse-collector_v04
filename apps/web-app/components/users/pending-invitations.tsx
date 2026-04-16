"use client";

import * as React from "react";
import { AlertTriangle, Ban } from "lucide-react";
import type { Invitation, Role } from "@/lib/users/types";
import { canRevokeInvitation } from "@/lib/users/rbac";
import { RoleBadge } from "./role-badge";
import { ConfirmDialog } from "./modal";

type Props = {
  invitations: Invitation[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  actorRole: Role;
  onRevoke: (invitationId: string) => Promise<void>;
};

/**
 * Lista de convites pendentes com acao de revogar. Oculta convites
 * accepted/revoked/expired (o backend ja filtra, mas defendemos aqui
 * caso envie tudo de uma vez).
 */
export function PendingInvitations({
  invitations,
  loading,
  error,
  onRetry,
  actorRole,
  onRevoke,
}: Props) {
  const pending = invitations.filter((i) => i.status === "pending");
  const [target, setTarget] = React.useState<Invitation | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  async function doRevoke() {
    if (!target) return;
    setSubmitting(true);
    try {
      await onRevoke(target.id);
      setTarget(null);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section
      aria-labelledby="pending-invites-heading"
      className="rounded-lg border border-border bg-card text-card-foreground shadow-sm"
    >
      <header className="border-b border-border px-4 py-3">
        <h2
          id="pending-invites-heading"
          className="text-sm font-semibold"
        >
          Convites pendentes
        </h2>
        <p className="text-xs text-muted-foreground">
          Links enviados por email aguardando aceite do destinatario.
        </p>
      </header>
      <div className="overflow-x-auto">
        <table
          className="w-full text-sm"
          aria-label="Convites pendentes"
        >
          <thead>
            <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <th scope="col" className="px-3 py-2">Email</th>
              <th scope="col" className="px-3 py-2">Papel</th>
              <th scope="col" className="px-3 py-2">Enviado</th>
              <th scope="col" className="px-3 py-2">Expira</th>
              <th scope="col" className="px-3 py-2 text-right">Acoes</th>
            </tr>
          </thead>
          <tbody aria-busy={loading || undefined}>
            {loading ? (
              <Skeleton cols={5} />
            ) : error ? (
              <tr>
                <td colSpan={5} className="px-3 py-10 text-center">
                  <div
                    role="alert"
                    className="inline-flex flex-col items-center gap-2 text-sm text-destructive"
                  >
                    <div className="inline-flex items-center gap-2">
                      <AlertTriangle aria-hidden="true" className="h-4 w-4" />
                      <span>{error}</span>
                    </div>
                    {onRetry ? (
                      <button
                        type="button"
                        onClick={onRetry}
                        className="inline-flex h-8 items-center rounded-md border border-border bg-background px-3 text-sm font-medium transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        Tentar novamente
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ) : pending.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  className="px-3 py-10 text-center text-sm text-muted-foreground"
                >
                  Nenhum convite pendente.
                </td>
              </tr>
            ) : (
              pending.map((inv) => {
                const decision = canRevokeInvitation(actorRole, inv.role);
                return (
                  <tr
                    key={inv.id}
                    className="border-b border-border last:border-b-0 hover:bg-accent/40"
                  >
                    <td className="px-3 py-2">{inv.email}</td>
                    <td className="px-3 py-2">
                      <RoleBadge role={inv.role} />
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {formatDate(inv.createdAt)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {inv.expiresAt ? formatDate(inv.expiresAt) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => setTarget(inv)}
                        disabled={!decision.allowed}
                        title={decision.allowed ? undefined : decision.reason}
                        aria-label={`Revogar convite de ${inv.email}`}
                        className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-background px-2 text-sm text-destructive transition hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <Ban className="h-3.5 w-3.5" aria-hidden="true" />
                        Revogar
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <ConfirmDialog
        open={Boolean(target)}
        title="Revogar convite"
        description={
          target
            ? `Deseja revogar o convite enviado para ${target.email}? O link se torna invalido imediatamente.`
            : ""
        }
        confirmLabel="Revogar"
        destructive
        loading={submitting}
        onCancel={() => setTarget(null)}
        onConfirm={doRevoke}
      />
    </section>
  );
}

function Skeleton({ cols }: { cols: number }) {
  return (
    <>
      {Array.from({ length: 3 }).map((_, i) => (
        <tr key={i} className="border-b border-border last:border-b-0">
          {Array.from({ length: cols }).map((__, j) => (
            <td key={j} className="px-3 py-2">
              <div
                aria-hidden="true"
                className="h-4 w-full animate-pulse rounded bg-muted"
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

function formatDate(value: string): string {
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString("pt-BR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}
