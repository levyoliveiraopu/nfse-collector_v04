/**
 * Schemas Zod para formularios de gestao de usuarios (APP-09).
 *
 * Apenas validacao do cliente — a autoridade final permanece no backend
 * (ticket API futuro), que reaplica RBAC e checa duplicidade.
 */
import { z } from "zod";
import { ROLES, type Role } from "./types";

const emailField = z
  .string()
  .min(1, "Informe um email.")
  .email("Informe um email valido.")
  .max(254, "Email muito longo.");

const roleField = z.enum(ROLES, {
  errorMap: () => ({ message: "Papel invalido." }),
});

/** Convite de novo membro. */
export const inviteMemberSchema = z.object({
  email: emailField,
  role: roleField,
});
export type InviteMemberInput = z.infer<typeof inviteMemberSchema>;

/** PATCH para alterar papel. */
export const updateMemberSchema = z.object({
  role: roleField,
});
export type UpdateMemberInput = z.infer<typeof updateMemberSchema>;

/** Aceitar convite (token vem pela URL). */
export const acceptInvitationSchema = z
  .object({
    name: z.string().min(2, "Informe seu nome.").max(120),
    password: z
      .string()
      .min(10, "Senha deve ter pelo menos 10 caracteres.")
      .max(256, "Senha muito longa."),
    confirm: z.string().min(1, "Confirme a senha."),
  })
  .refine((data) => data.password === data.confirm, {
    message: "As senhas nao conferem.",
    path: ["confirm"],
  });
export type AcceptInvitationInput = z.infer<typeof acceptInvitationSchema>;

/** Util: lista de papeis que um ator pode escolher ao convidar/promover. */
export function rolesAssignableBy(actor: Role): Role[] {
  // admin nao convida/promove a `owner` nem a `admin` (apenas owner pode).
  if (actor === "owner") return ["owner", "admin", "operator", "viewer"];
  if (actor === "admin") return ["operator", "viewer"];
  return [];
}
