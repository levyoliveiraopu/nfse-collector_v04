/**
 * Schemas Zod dos formularios de autenticacao (APP-01).
 * Espelham as regras minimas dos schemas Pydantic em
 * apps/api/api/auth/schemas.py sem duplicar validacoes de servidor.
 */
import { z } from "zod";

const password = z
  .string()
  .min(10, "Senha deve ter pelo menos 10 caracteres.")
  .max(256, "Senha muito longa.");

export const loginSchema = z.object({
  email: z.string().email("Informe um email valido."),
  password: z.string().min(1, "Informe sua senha.").max(256),
  tenant_slug: z
    .string()
    .trim()
    .regex(
      /^[a-z0-9][a-z0-9-]{0,58}[a-z0-9]$/,
      "Slug deve conter apenas letras minusculas, numeros e hifens.",
    )
    .optional()
    .or(z.literal("")),
});
export type LoginInput = z.infer<typeof loginSchema>;

export const signupSchema = z.object({
  tenant_name: z
    .string()
    .min(2, "Nome da empresa muito curto.")
    .max(120, "Nome da empresa muito longo."),
  tenant_slug: z
    .string()
    .min(2)
    .max(60)
    .regex(
      /^[a-z0-9][a-z0-9-]{0,58}[a-z0-9]$/,
      "Slug deve conter apenas letras minusculas, numeros e hifens.",
    ),
  name: z.string().min(2, "Informe seu nome.").max(120),
  email: z.string().email("Informe um email valido."),
  password,
  accept_terms: z.literal(true, {
    errorMap: () => ({ message: "Voce precisa aceitar os termos." }),
  }),
});
export type SignupInput = z.infer<typeof signupSchema>;

export const recoverPasswordSchema = z.object({
  email: z.string().email("Informe um email valido."),
});
export type RecoverPasswordInput = z.infer<typeof recoverPasswordSchema>;

export const resetPasswordSchema = z
  .object({
    password,
    confirm: z.string().min(1, "Confirme a senha."),
  })
  .refine((data) => data.password === data.confirm, {
    message: "As senhas nao conferem.",
    path: ["confirm"],
  });
export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>;

export const acceptInviteSchema = z
  .object({
    name: z.string().min(2, "Informe seu nome.").max(120),
    password,
    confirm: z.string().min(1, "Confirme a senha."),
  })
  .refine((data) => data.password === data.confirm, {
    message: "As senhas nao conferem.",
    path: ["confirm"],
  });
export type AcceptInviteInput = z.infer<typeof acceptInviteSchema>;
