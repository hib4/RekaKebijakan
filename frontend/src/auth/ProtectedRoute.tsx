import { useEffect } from "react";
import type { ReactNode } from "react";
import { useAuth } from "./useAuth";
import { navigate } from "./navigation";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { loading, user } = useAuth();

  useEffect(() => {
    if (loading || user) return;
    const next = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    navigate(`/login?next=${encodeURIComponent(next)}`, true);
  }, [loading, user]);

  if (loading) {
    return (
      <main className="auth-loading" aria-live="polite">
        <span className="auth-loading-mark" aria-hidden="true">RK</span>
        <p>Memeriksa sesi Anda...</p>
      </main>
    );
  }

  if (!user) {
    return null;
  }

  return children;
}
