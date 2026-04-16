"use client";

import * as React from "react";
import { UserPlus } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth/auth-provider";
import { InviteDialog } from "@/components/users/invite-dialog";
import { MembersTable } from "@/components/users/members-table";
import { PendingInvitations } from "@/components/users/pending-invitations";
import {
  ApiError,
  inviteMember,
  listInvitations,
  listMembers,
  removeMember,
  revokeInvitation,
  updateMemberRole,
} from "@/lib/users/api-client";
import { isManager } from "@/lib/users/rbac";
import type { Invitation, Member, Role } from "@/lib/users/types";
import type { InviteMemberInput } from "@/lib/users/schemas";

export default function UsuariosPage() {
  const { user, accessToken, refresh } = useAuth();
  const actorRole = (user?.role as Role) ?? "viewer";
  const actorIsManager = isManager(actorRole);

  const [members, setMembers] = React.useState<Member[]>([]);
  const [invites, setInvites] = React.useState<Invitation[]>([]);
  const [membersLoading, setMembersLoading] = React.useState(true);
  const [invitesLoading, setInvitesLoading] = React.useState(true);
  const [membersError, setMembersError] = React.useState<string | null>(null);
  const [invitesError, setInvitesError] = React.useState<string | null>(null);
  const [inviteOpen, setInviteOpen] = React.useState(false);

  const ctx = React.useMemo(
    () => ({
      accessToken,
      onTokenRefreshed: () => {
        void refresh();
      },
    }),
    [accessToken, refresh],
  );

  const loadMembers = React.useCallback(async () => {
    setMembersLoading(true);
    setMembersError(null);
    try {
      const data = await listMembers(ctx);
      setMembers(data);
    } catch (err) {
      setMembersError(extractMessage(err));
    } finally {
      setMembersLoading(false);
    }
  }, [ctx]);

  const loadInvites = React.useCallback(async () => {
    setInvitesLoading(true);
    setInvitesError(null);
    try {
      const data = await listInvitations(ctx);
      setInvites(data);
    } catch (err) {
      setInvitesError(extractMessage(err));
    } finally {
      setInvitesLoading(false);
    }
  }, [ctx]);

  React.useEffect(() => {
    void loadMembers();
    void loadInvites();
  }, [loadMembers, loadInvites]);

  async function handleInvite(input: InviteMemberInput) {
    const created = await inviteMember(ctx, input);
    setInvites((current) => [created, ...current]);
  }

  async function handleChangeRole(userId: string, newRole: Role) {
    try {
      const updated = await updateMemberRole(ctx, userId, newRole);
      setMembers((current) =>
        current.map((m) => (m.userId === userId ? updated : m)),
      );
      toast.success("Papel atualizado.");
    } catch (err) {
      toast.error(extractMessage(err));
      throw err;
    }
  }

  async function handleRemove(userId: string) {
    try {
      await removeMember(ctx, userId);
      setMembers((current) => current.filter((m) => m.userId !== userId));
      toast.success("Usuario removido.");
    } catch (err) {
      toast.error(extractMessage(err));
      throw err;
    }
  }

  async function handleRevoke(invitationId: string) {
    try {
      await revokeInvitation(ctx, invitationId);
      setInvites((current) =>
        current.map((i) =>
          i.id === invitationId ? { ...i, status: "revoked" } : i,
        ),
      );
      toast.success("Convite revogado.");
    } catch (err) {
      toast.error(extractMessage(err));
      throw err;
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Usuarios</h1>
          <p className="text-sm text-muted-foreground">
            Gerencie quem tem acesso ao tenant, papeis e convites pendentes.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setInviteOpen(true)}
          disabled={!actorIsManager}
          title={
            actorIsManager
              ? undefined
              : "Apenas owner ou admin podem convidar usuarios"
          }
          className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
        >
          <UserPlus className="h-4 w-4" aria-hidden="true" />
          Convidar usuario
        </button>
      </header>

      <MembersTable
        members={members}
        loading={membersLoading}
        error={membersError}
        onRetry={() => void loadMembers()}
        actorRole={actorRole}
        actorUserId={user?.userId ?? ""}
        onChangeRole={handleChangeRole}
        onRemove={handleRemove}
      />

      <PendingInvitations
        invitations={invites}
        loading={invitesLoading}
        error={invitesError}
        onRetry={() => void loadInvites()}
        actorRole={actorRole}
        onRevoke={handleRevoke}
      />

      <InviteDialog
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        actorRole={actorRole}
        onSubmit={handleInvite}
      />
    </div>
  );
}

function extractMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.detail && typeof err.detail === "object" && "detail" in err.detail) {
      const detail = (err.detail as { detail?: unknown }).detail;
      if (typeof detail === "string") return detail;
    }
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return "Erro inesperado.";
}
