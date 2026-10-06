import { useCallback, useState } from "react";

const SESSION_KEY = "fashion-chatbot.session_id";
const ADMIN_TOKEN_KEY = "fashion-chatbot.admin_token";

function newId(): string {
  return crypto.randomUUID();
}

export function useSession() {
  const [sessionId, setSessionId] = useState<string>(() => {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const id = newId();
    localStorage.setItem(SESSION_KEY, id);
    return id;
  });

  const reset = useCallback(() => {
    const id = newId();
    localStorage.setItem(SESSION_KEY, id);
    setSessionId(id);
  }, []);

  return { sessionId, reset };
}

export function useAdminToken() {
  const [token, setToken] = useState<string | null>(() =>
    sessionStorage.getItem(ADMIN_TOKEN_KEY)
  );

  const save = useCallback((t: string) => {
    sessionStorage.setItem(ADMIN_TOKEN_KEY, t);
    setToken(t);
  }, []);

  const clear = useCallback(() => {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    setToken(null);
  }, []);

  return { token, save, clear };
}