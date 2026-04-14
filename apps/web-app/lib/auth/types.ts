/**
 * Tipos compartilhados do fluxo de autenticacao (APP-01).
 */

export type AuthUser = {
  userId: string;
  tenantId: string;
  role: string;
};

/** Par acess+refresh devolvido pelo back (API-02). */
export type AuthTokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  tenant_id: string;
  user_id: string;
  role: string;
};

/** Payload simplificado devolvido pelos Route Handlers do Next.
 *  O refresh fica no cookie httpOnly e NAO volta no body. */
export type AuthSessionPayload = {
  access_token: string;
  expires_in: number;
  user: AuthUser;
};
