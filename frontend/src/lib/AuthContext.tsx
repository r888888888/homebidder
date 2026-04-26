import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import {
  clearToken,
  fetchCurrentUser,
  getToken,
  login as authLogin,
  register as authRegister,
  setToken,
  type UserRead,
} from "./auth";

interface AuthContextValue {
  user: UserRead | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  loginWithToken: (token: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount: validate any stored token.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const hadToken = Boolean(getToken());
      const u = await fetchCurrentUser();
      if (!cancelled) {
        if (u) {
          setUser(u);
        } else if (hadToken) {
          // Had a token but it was invalid/expired — clear it.
          clearToken();
        }
        setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const token = await authLogin(email, password);
    setToken(token);
    const u = await fetchCurrentUser();
    setUser(u);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    await authRegister(email, password);
    // Auto-login after successful registration.
    const token = await authLogin(email, password);
    setToken(token);
    const u = await fetchCurrentUser();
    setUser(u);
  }, []);

  const loginWithToken = useCallback(async (token: string) => {
    setToken(token);
    const u = await fetchCurrentUser();
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, loginWithToken, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
