/**
 * Tipos compartilhados para gestao de usuarios do tenant (APP-09).
 * Espelham o que a API (ticket API futuro) devolvera para
 * `GET /tenant/members` e `GET /tenant/invitations`.
 */

/** Papeis suportados — alinhados com `apps/api/api/security/rbac.py`. */
export const ROLES = ["owner", "admin", "operator", "viewer"] as const;
export type Role = (typeof ROLES)[number];

export type MemberStatus = "active" | "disabled";

/** Linha da lista de membros. */
export type Member = {
  userId: string;
  email: string;
  name: string;
  role: Role;
  status: MemberStatus;
  /** ISO8601 UTC ou null se o usuario nunca logou. */
  lastLoginAt: string | null;
  /** ISO8601 UTC da criacao da membership. */
  createdAt: string;
};

export type InvitationStatus = "pending" | "accepted" | "revoked" | "expired";

/** Convite pendente emitido pelo tenant. */
export type Invitation = {
  id: string;
  email: string;
  role: Role;
  status: InvitationStatus;
  /** ISO8601 UTC. */
  createdAt: string;
  /** ISO8601 UTC — null quando o convite nao tem validade (nao deve acontecer). */
  expiresAt: string | null;
  /** email do membro que emitiu o convite. */
  invitedByEmail: string | null;
};
