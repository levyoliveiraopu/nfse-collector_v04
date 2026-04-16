"use client";

import * as React from "react";
import { AlertTriangle, MoreVertical, Trash2, UserCog } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Member, Role } from "@/lib/users/types";
import { canChangeRole, canRemoveMember } from "@/lib/users/rbac";
import { RoleBadge, roleLabel } from "./role-badge";
import { RoleSelect } from "./role-select";
import { Modal, ConfirmDialog } from "./modal";

type MembersTableProps = {
  members: Member[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  actorRole: Role;
  /** userId do ator — usado para proteger "remover a si mesmo". */
  actorUserId: string;
  onChangeRole: (userId: string, newRole: Role) => Promise<void>;
  onRemove: (userId: string) => Promise<void>;
};

/**
 * Lista de membros do tenant. Sem paginacao/filtro server-side (APP-09
 * cobre um recurso de baixa cardinalidade; se passar de 200 membros
 * migramos para `<DataTable>`).
 */
export function MembersTable({
  members,
  loading,
  error,
  onRetry,
  actorRole,
  actorUserId,
  onChangeRole,
  onRemove,
}: MembersTableProps) {
  const [roleDialog, setRoleDialog] = React.useState<Member | null>(null);
  const [removeDialog, setRemoveDialog] = React.useState<Member | null>(null);
  const [pending, setPending] = React.useState(false);

  async function submitRoleChange(newRole: Role) {
    if (!roleDialog) return;
    setPending(true);
    try {
      await onChangeRole(roleDialog.userId, newRole);
      setRoleDialog(null);
    } finally {
      setPending(false);
    }
  }

  async function submitRemove() {
    if (!removeDialog) return;
    setPending(true);
    try {
      await onRemove(removeDialog.userId);
      setRemoveDialog(null);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card text-card-foreground shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" aria-label="Usuarios do tenant">
          <thead>
            <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <th scope="col" className="px-3 py-2">Nome</th>
              <th scope="col" className="px-3 py-2">Email</th>
              <th scope="col" className="px-3 py-2">Papel</th>
              <th scope="col" className="px-3 py-2">Status</th>
              <th scope="col" className="px-3 py-2">Ultimo login</th>
              <th scope="col" className="px-3 py-2 text-right">Acoes</th>
            </tr>
          </thead>
          <tbody aria-busy={loading || undefined}>
            {loading ? (
              <SkeletonRows cols={6} />
            ) : error ? (
              <tr>
                <td colSpan={6} className="px-3 py-10 text-center">
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
            ) : members.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-3 py-10 text-center text-sm text-muted-foreground"
                >
                  Nenhum usuario cadastrado neste tenant.
                </td>
              </tr>
            ) : (
              members.map((m) => (
                <MemberRow
                  key={m.userId}
                  member={m}
                  actorRole={actorRole}
                  isSelf={m.userId === actorUserId}
                  onEditRole={() => setRoleDialog(m)}
                  onRemove={() => setRemoveDialog(m)}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {roleDialog ? (
        <ChangeRoleModal
          member={roleDialog}
          actorRole={actorRole}
          pending={pending}
          onClose={() => setRoleDialog(null)}
          onSubmit={submitRoleChange}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(removeDialog)}
        title="Remover usuario"
        description={
          removeDialog
            ? `Deseja remover ${removeDialog.name} (${removeDialog.email}) deste tenant? O usuario perde acesso imediatamente.`
            : ""
        }
        confirmLabel="Remover"
        destructive
        loading={pending}
        onCancel={() => setRemoveDialog(null)}
        onConfirm={submitRemove}
      />
    </div>
  );
}

function MemberRow({
  member,
  actorRole,
  isSelf,
  onEditRole,
  onRemove,
}: {
  member: Member;
  actorRole: Role;
  isSelf: boolean;
  onEditRole: () => void;
  onRemove: () => void;
}) {
  // Decide disponibilidade no UI — backend reaplica RBAC.
  const canEditRoleDecision = canChangeRole(actorRole, member.role, member.role);
  const canRemoveDecision = canRemoveMember(actorRole, member.role);
  const canEditRole = canEditRoleDecision.allowed && !isSelf;
  const canRemove = canRemoveDecision.allowed && !isSelf;
  const disabledReason = isSelf
    ? "Voce nao pode gerenciar a si mesmo aqui"
    : !canRemoveDecision.allowed
      ? canRemoveDecision.reason
      : !canEditRoleDecision.allowed
        ? canEditRoleDecision.reason
        : undefined;

  return (
    <tr className="border-b border-border last:border-b-0 hover:bg-accent/40">
      <td className="px-3 py-2">{member.name}</td>
      <td className="px-3 py-2 text-muted-foreground">{member.email}</td>
      <td className="px-3 py-2">
        <RoleBadge role={member.role} />
      </td>
      <td className="px-3 py-2">
        <span
          className={cn(
            "inline-flex items-center rounded-md border px-2 py-0.5 text-xs",
            member.status === "active"
              ? "border-success/30 bg-success/10 text-success"
              : "border-border bg-muted text-muted-foreground",
          )}
        >
          {member.status === "active" ? "Ativo" : "Desabilitado"}
        </span>
      </td>
      <td className="px-3 py-2 tabular-nums text-muted-foreground">
        {formatLastLogin(member.lastLoginAt)}
      </td>
      <td className="px-3 py-2 text-right">
        <RowActions
          onEditRole={canEditRole ? onEditRole : undefined}
          onRemove={canRemove ? onRemove : undefined}
          disabledReason={disabledReason}
          memberLabel={member.name}
        />
      </td>
    </tr>
  );
}

function RowActions({
  onEditRole,
  onRemove,
  disabledReason,
  memberLabel,
}: {
  onEditRole?: () => void;
  onRemove?: () => void;
  disabledReason?: string;
  memberLabel: string;
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const noActions = !onEditRole && !onRemove;

  return (
    <div ref={ref} className="relative inline-flex">
      <button
        type="button"
        aria-label={`Acoes para ${memberLabel}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-disabled={noActions || undefined}
        disabled={noActions}
        title={disabledReason}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40"
      >
        <MoreVertical className="h-4 w-4" aria-hidden="true" />
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-9 z-30 w-48 rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md"
        >
          {onEditRole ? (
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onEditRole();
              }}
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent focus-visible:outline-none focus-visible:bg-accent"
            >
              <UserCog className="h-4 w-4" aria-hidden="true" />
              Alterar papel
            </button>
          ) : null}
          {onRemove ? (
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onRemove();
              }}
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm text-destructive hover:bg-destructive/10 focus-visible:outline-none focus-visible:bg-destructive/10"
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
              Remover usuario
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function ChangeRoleModal({
  member,
  actorRole,
  pending,
  onClose,
  onSubmit,
}: {
  member: Member;
  actorRole: Role;
  pending: boolean;
  onClose: () => void;
  onSubmit: (newRole: Role) => Promise<void>;
}) {
  const [role, setRole] = React.useState<Role>(member.role);
  const decision = canChangeRole(actorRole, member.role, role);

  return (
    <Modal
      open
      onClose={onClose}
      title={`Alterar papel de ${member.name}`}
      description={`Papel atual: ${roleLabel(member.role)}.`}
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (decision.allowed && role !== member.role) {
            void onSubmit(role);
          }
        }}
      >
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Novo papel</span>
          <RoleSelect
            value={role}
            actor={actorRole}
            onChange={setRole}
            aria-label="Novo papel do usuario"
          />
        </label>
        {!decision.allowed ? (
          <p role="alert" className="text-xs text-destructive">
            {decision.reason}
          </p>
        ) : null}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={pending || !decision.allowed || role === member.role}
            className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground shadow-sm transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
          >
            {pending ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function SkeletonRows({ cols }: { cols: number }) {
  return (
    <>
      {Array.from({ length: 4 }).map((_, i) => (
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

function formatLastLogin(value: string | null): string {
  if (!value) return "Nunca";
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
