import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { Brand } from "../Header/Header";
import { useAuth } from "../../auth/useAuth";
import { authStorageKey } from "../../auth/storageNamespace";
import "./AppShell.css";

const productNav = [
  ["/dashboard", "Dashboard", "dashboard"],
  ["/projects", "Proyek Kebijakan", "projects"],
  ["/reports", "Laporan", "reports"],
] as const;

type ProductNavIconType = (typeof productNav)[number][2];

function ProductNavIcon({ type }: { type: ProductNavIconType }) {
  if (type === "dashboard") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M4 4h16v16H4z" />
        <path d="m7 15 4-6 6 4" />
        <circle className="nav-icon-node" cx="7" cy="15" r="1.4" />
        <circle className="nav-icon-node" cx="11" cy="9" r="1.4" />
        <circle className="nav-icon-node" cx="17" cy="13" r="1.4" />
      </svg>
    );
  }
  if (type === "projects") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M3 4h7l2 3h9v13H3z" />
        <path d="M7 12h10M7 16h7" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M4 3h11l5 5v13H4z" />
      <path d="M15 3v5h5" />
      <path d="M8 12h8M8 16h8" />
    </svg>
  );
}

type AppShellProps = {
  title: string;
  subtitle: string;
  eyebrow?: string;
  actions?: ReactNode;
  children: ReactNode;
};

export function AppShell({ title, subtitle, eyebrow = "Menu", actions, children }: AppShellProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname: path } = useLocation();
  const sidebarKey = authStorageKey("sidebar-collapsed");
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(sidebarKey) === "true");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [logoutError, setLogoutError] = useState("");

  useEffect(() => {
    const close = (event: KeyboardEvent) => event.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", close);
    return () => {
      window.removeEventListener("keydown", close);
    };
  }, []);

  const nav = (
    <nav className="app-sidebar-nav" aria-label="Navigasi produk">
      {productNav.map(([href, label, icon]) => {
        const active = path === href || (href !== "/dashboard" && path.startsWith(`${href}/`));
        return (
          <NavLink
            className={active ? "active" : ""}
            to={href}
            key={href}
            onClick={() => {
              setDrawerOpen(false);
            }}
          >
            <span aria-hidden="true"><ProductNavIcon type={icon} /></span>
            <b>{label}</b>
          </NavLink>
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
            <Link to="/dashboard">Menu</Link>
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
          <Link className="button primary" to="/dashboard">Kembali ke Dashboard</Link>
        </div>
      </section>
    </AppShell>
  );
}
