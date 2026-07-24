import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  ApiError,
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
} from "../api/client";
import type { AuthUser } from "../api/client";
import { AuthContext } from "./auth-context";
import type { AuthContextValue } from "./auth-context";
import { setAuthStorageNamespace } from "./storageNamespace";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getCurrentUser()
      .then((currentUser) => {
        if (!active) return;
        setAuthStorageNamespace(currentUser.id);
        setUser(currentUser);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) return;
        console.error("Unable to restore the authentication session", error);
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const expireSession = () => {
      setAuthStorageNamespace(null);
      setUser(null);
    };
    window.addEventListener("auth-session-expired", expireSession);
    return () => window.removeEventListener("auth-session-expired", expireSession);
  }, []);

  const establishSession = (currentUser: AuthUser) => {
    setAuthStorageNamespace(currentUser.id);
    setUser(currentUser);
    return currentUser;
  };

  const value: AuthContextValue = {
    user,
    loading,
    login: (input) => loginUser(input).then(establishSession),
    register: (input) => registerUser(input).then(establishSession),
    logout: async () => {
      await logoutUser();
      setAuthStorageNamespace(null);
      setUser(null);
    },
  };

  return <AuthContext value={value}>{children}</AuthContext>;
}
