/**
 * Guardas de RBAC para UI de gestao de membros (APP-09).
 *
 * Espelham `ensure_can_manage_member` em
 * `apps/api/api/security/rbac.py` para dar feedback imediato no cliente,
 * desabilitando botoes em vez de depender somente de 403 da API. A
 * autoridade final permanece no backend.
 */
import type { Role } from "./types";
import { rolesAssignableBy } from "./schemas";

const RANK: Record<Role, number> = {
  viewer: 1,
  operator: 2,
  admin: 3,
  owner: 4,
};

export function roleRank(role: Role): number {
  return RANK[role];
}

export function isManager(role: Role): boolean {
  return role === "owner" || role === "admin";
}

export type Decision = { allowed: true } | { allowed: false; reason: string };

/** Pode remover um membro com papel `target`?
 *
 * Regras (matriz em `docs/architecture/rbac-matrix.md`):
 * - Apenas owner/admin gerenciam membros.
 * - Owner so e tocado por outro owner.
 */
export function canRemoveMember(actor: Role, target: Role): Decision {
  if (!isManager(actor)) {
    return {
      allowed: false,
      reason: "apenas owner ou admin podem gerenciar membros",
    };
  }
  if (target === "owner" && actor !== "owner") {
    return {
      allowed: false,
      reason: "apenas um owner pode gerenciar outro owner",
    };
  }
  return { allowed: true };
}

/** Pode alterar o papel do membro `target` para `newRole`?
 *
 * Regras:
 * - Apenas owner/admin gerenciam membros.
 * - Owner so e alterado por outro owner.
 * - Ator so pode atribuir papeis em `rolesAssignableBy(actor)` — isso
 *   garante "admin nao promove a admin/owner" conforme matriz.
 */
export function canChangeRole(
  actor: Role,
  target: Role,
  newRole: Role,
): Decision {
  if (!isManager(actor)) {
    return {
      allowed: false,
      reason: "apenas owner ou admin podem gerenciar membros",
    };
  }
  if (target === "owner" && actor !== "owner") {
    return {
      allowed: false,
      reason: "apenas um owner pode gerenciar outro owner",
    };
  }
  if (!rolesAssignableBy(actor).includes(newRole)) {
    return {
      allowed: false,
      reason: `ator com papel '${actor}' nao pode atribuir '${newRole}'`,
    };
  }
  return { allowed: true };
}

/** Pode convidar um novo membro com papel `role`?
 *
 * Admin so convida operator/viewer; owner convida qualquer papel (veja
 * matriz). Espelha `rolesAssignableBy`.
 */
export function canInviteWithRole(actor: Role, role: Role): Decision {
  if (!isManager(actor)) {
    return {
      allowed: false,
      reason: "apenas owner ou admin podem gerenciar membros",
    };
  }
  if (!rolesAssignableBy(actor).includes(role)) {
    return {
      allowed: false,
      reason: `ator com papel '${actor}' nao pode atribuir '${role}'`,
    };
  }
  return { allowed: true };
}

/** Pode revogar um convite pendente? Regras equivalentes ao remover membro. */
export function canRevokeInvitation(
  actor: Role,
  invitationRole: Role,
): Decision {
  return canRemoveMember(actor, invitationRole);
}
