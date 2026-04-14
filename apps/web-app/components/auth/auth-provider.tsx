"use client";

/**
 * AuthProvider (APP-01)
 *
 * - `user` + `access_token` ficam em memoria (nao em localStorage) para
 *   mitigar XSS.
 * - O refresh token vive num cookie httpOnly setado pelos Route Handlers
 *   em `app/api/auth/*` — o client nunca o ve.
 * - Ao montar, tenta `POST /api/auth/refresh` uma vez para rehidratar a
 *   sessao (o cookie sobrevive ao reload).
 * - Agenda refresh automatico ~60s antes do access expirar.
 * - Logout limpa estado + cookie.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  login as loginRequest,
  logout as logoutRequest,
  signup as signupRequest,
  tryRefresh,
} from "@/lib/auth/api-client";
import type { AuthSessionPayload, AuthUser } from "@/lib/auth/types";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  accessToken: string | null;
  login: (input: { email: string; password: string }) => Promise<void>;
  signup: (input: {
    tenant_name: string;
    tenant_slug: string;
    name: string;
    email: string;
    password: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  /** Dispara refresh manual (util em testes). */
  refresh: () => Promise<boolean>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

/** Segundos antes da expiracao em que agendamos um refresh proativo. */
const REFRESH_SAFETY_MARGIN_SECONDS = 60;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const applySession = useCallback(
    (payload: AuthSessionPayload) => {
      setAccessToken(payload.access_token);
      setUser(payload.user);
      setStatus("authenticated");
      clearTimer();
      const marginMs =
        Math.max(payload.expires_in - REFRESH_SAFETY_MARGIN_SECONDS, 5) * 1000;
      timerRef.current = setTimeout(() => {
        void refreshInternal();
      }, marginMs);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [clearTimer],
  );

  const clearSession = useCallback(() => {
    clearTimer();
    setAccessToken(null);
    setUser(null);
    setStatus("unauthenticated");
  }, [clearTimer]);

  const refreshInternal = useCallback(async (): Promise<boolean> => {
    const payload = await tryRefresh();
    if (!payload) {
      clearSession();
      return false;
    }
    applySession(payload);
    return true;
  }, [applySession, clearSession]);

  // Rehidrata sessao ao montar.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const payload = await tryRefresh();
      if (cancelled) return;
      if (payload) {
        applySession(payload);
      } else {
        setStatus("unauthenticated");
      }
    })();
    return () => {
      cancelled = true;
      clearTimer();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback<AuthContextValue["login"]>(
    async (input) => {
      const payload = await loginRequest(input);
      applySession(payload);
    },
    [applySession],
  );

  const signup = useCallback<AuthContextValue["signup"]>(
    async (input) => {
      const payload = await signupRequest(input);
      applySession(payload);
    },
    [applySession],
  );

  const logout = useCallback<AuthContextValue["logout"]>(async () => {
    await logoutRequest();
    clearSession();
  }, [clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      accessToken,
      login,
      signup,
      logout,
      refresh: refreshInternal,
    }),
    [status, user, accessToken, login, signup, logout, refreshInternal],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth deve ser usado dentro de <AuthProvider>.");
  }
  return ctx;
}
