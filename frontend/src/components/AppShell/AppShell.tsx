import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Brand } from "../Header/Header";
import { useAuth } from "../../auth/useAuth";
import { authStorageKey } from "../../auth/storageNamespace";
import "./AppShell.css";

const productNav = [
  ["/dashboard", "Dashboard", "D"],
  ["/projects", "Proyek Kebijakan", "P"],
  ["/reports", "Laporan", "L"],
] as const;

type AppShellProps = {
  title: string;
  subtitle: string;
  eyebrow?: string;
  actions?: ReactNode;
  children: ReactNode;
};

function navigate(path: string) {
  window.history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function AppShell({ title, subtitle, eyebrow = "Menu", actions, children }: AppShellProps) {
  const { user, logout } = useAuth();
  const sidebarKey = authStorageKey("sidebar-collapsed");
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(sidebarKey) === "true");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const [logoutError, setLogoutError] = useState("");

  useEffect(() => {
    const handlePopState = () => setCurrentPath(window.location.pathname);
    const close = (event: KeyboardEvent) => event.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("popstate", handlePopState);
    window.addEventListener("keydown", close);
    return () => {
      window.removeEventListener("popstate", handlePopState);
      window.removeEventListener("keydown", close);
    };
  }, []);

  const path = currentPath;

  const nav = (
    <nav className="app-sidebar-nav" aria-label="Navigasi produk">
      {productNav.map(([href, label, icon]) => {
        const active = path === href || (href !== "/dashboard" && path.startsWith(`${href}/`));
        return (
          <a
            className={active ? "active" : ""}
            href={href}
            key={href}
            onClick={(event) => {
              event.preventDefault();
              setDrawerOpen(false);
              navigate(href);
            }}
          >
            <span aria-hidden="true">{icon}</span>
            <b>{label}</b>
          </a>
        );
      })}
    </nav>
  );

  return (
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="app-sidebar" aria-label="Sidebar produk">
        <div className="app-sidebar-brand"><Brand /></div>
        {nav}
        <button
          className="sidebar-toggle"
          onClick={() => setCollapsed((prev) => {
            const next = !prev;
            localStorage.setItem(sidebarKey, String(next));
            return next;
          })}
          aria-pressed={collapsed}
          aria-label={collapsed ? "Perluas sidebar" : "Ciutkan sidebar"}
        >
          {collapsed ? (
            <svg fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" width="16" height="16">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          ) : (
            <svg fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" width="16" height="16">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          )}
        </button>
      </aside>
      {drawerOpen && <button className="app-drawer-backdrop" aria-label="Tutup navigasi" onClick={() => setDrawerOpen(false)} />}
      <div className={`app-drawer ${drawerOpen ? "open" : ""}`}>
        <div className="app-sidebar-brand"><Brand /></div>
        {nav}
      </div>
      <div className="app-workspace">
        <header className="app-topbar">
          <button className="menu-button app-menu-button" aria-label="Buka navigasi produk" aria-expanded={drawerOpen} onClick={() => setDrawerOpen(!drawerOpen)}>
            <span /><span /><span />
          </button>
          <div className="breadcrumb" aria-label="Breadcrumb">
            <a href="/dashboard" onClick={(event) => { event.preventDefault(); navigate("/dashboard"); }}>Menu</a>
            <span aria-hidden="true">/</span>
            <span>{title}</span>
          </div>
          <div className="topbar-account">
            <span title={user?.email}>{user?.name || user?.email}</span>
            <button onClick={async () => {
              setLogoutError("");
              try {
                await logout();
                navigate("/login");
              } catch (error) {
                setLogoutError(error instanceof Error ? error.message : "Gagal keluar dari akun.");
              }
            }}>Keluar</button>
          </div>
        </header>
        {logoutError && <p className="app-auth-error" role="alert">{logoutError}</p>}
        <main className="app-main">
          <section className="app-page-header" aria-labelledby="app-page-title">
            <div>
              <p className="eyebrow">{eyebrow}</p>
              <h1 id="app-page-title">{title}</h1>
              <p>{subtitle}</p>
            </div>
            {actions && <div className="actions">{actions}</div>}
          </section>
          {children}
        </main>
      </div>
    </div>
  );
}

export function PlaceholderPage({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <AppShell title={title} subtitle={subtitle}>
      <section className="dashboard-panel">
        <div className="state-block">
          <h2>{title} belum memiliki konten rinci.</h2>
          <p>Halaman ini disiapkan sebagai ruang kerja prototipe untuk pengembangan fitur berikutnya.</p>
          <button className="button primary" onClick={() => navigate("/dashboard")}>Kembali ke Dashboard</button>
        </div>
      </section>
    </AppShell>
  );
}
