import { apiBase } from "./api";

const TOKEN_KEY = "hb_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface UserRead {
  id: string;
  email: string;
  is_active: boolean;
}

export async function fetchCurrentUser(): Promise<UserRead | null> {
  const token = getToken();
  if (!token) return null;
  try {
    const resp = await fetch(`${apiBase}/api/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

export async function login(email: string, password: string): Promise<string> {
  const resp = await fetch(`${apiBase}/api/auth/jwt/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail ?? "Login failed");
  }
  const data = await resp.json();
  return data.access_token as string;
}

export async function register(email: string, password: string): Promise<void> {
  const resp = await fetch(`${apiBase}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const detail = body.detail ?? "Registration failed";
    if (detail === "REGISTER_USER_ALREADY_EXISTS") {
      throw new Error("An account with that email already exists.");
    }
    throw new Error(detail);
  }
}
