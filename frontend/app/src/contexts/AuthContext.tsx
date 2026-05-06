import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { clearStoredCredentials, readStoredCredentials, writeStoredCredentials } from "../lib/storage";

interface AuthContextValue {
  apiKey: string;
  userId: string;
  isAuthenticated: boolean;
  login: (apiKey: string, userId: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [credentials, setCredentials] = useState(readStoredCredentials);

  const login = useCallback(
    (apiKey: string, userId: string) => {
      writeStoredCredentials(apiKey, userId);
      setCredentials({ apiKey: apiKey.trim(), userId: userId.trim() });
      queryClient.clear();
    },
    [queryClient]
  );

  const logout = useCallback(() => {
    clearStoredCredentials();
    setCredentials({ apiKey: "", userId: "" });
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      apiKey: credentials.apiKey,
      userId: credentials.userId,
      isAuthenticated: Boolean(credentials.apiKey),
      login,
      logout
    }),
    [credentials.apiKey, credentials.userId, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
