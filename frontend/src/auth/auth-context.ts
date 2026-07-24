import { createContext } from "react";
import type { AuthUser } from "../api/client";

export type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  login: (input: { email: string; password: string }) => Promise<AuthUser>;
  register: (input: { name: string; email: string; password: string }) => Promise<AuthUser>;
  logout: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);
