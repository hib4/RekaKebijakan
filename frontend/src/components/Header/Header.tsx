import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { navigation } from "../../data/content";
import { useAuth } from "../../auth/useAuth";
import "./Header.css";

const scrollTo = (id: string) => {
  const element = document.getElementById(id);
  if (element) {
    element.scrollIntoView({ behavior: "smooth" });
  }
};

const quickDemoPath = "/simulation/demo-registrasi-umkm?step=graph&mode=split";

export function Brand() {
  const navigate = useNavigate();
  return (
    <a
      className="brand"
      href="/"
      aria-label="RekaKebijakan, kembali ke awal"
      onClick={(e) => {
        e.preventDefault();
        navigate("/");
        scrollTo("utama");
      }}
    >
      <img
        className="brand-mark"
        src="/reka-kebijakan-mark.svg"
        alt=""
        aria-hidden="true"
      />
      <b>RekaKebijakan</b>
    </a>
  );
}

interface HeaderProps {
  isDashboard?: boolean;
}

export default function Header({ isDashboard = false }: HeaderProps) {
  const navigate = useNavigate();
  const { loading, user } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeNav, setActiveNav] = useState("");

  useEffect(() => {
    if (isDashboard) return;

    const sections = [
      document.getElementById("hero"),
      ...navigation.map(([, id]) => document.getElementById(id)),
    ].filter(Boolean) as HTMLElement[];

    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            if (entry.target.id === "hero") {
              setActiveNav("tentang");
            } else {
              setActiveNav(entry.target.id);
            }
          }
        }),
      { rootMargin: "-35% 0px -55% 0px" },
    );

    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [isDashboard]);

  const handleDashboardClick = (e: React.MouseEvent) => {
    e.preventDefault();
    setMenuOpen(false);
    navigate("/dashboard");
  };

  const handleProjectsClick = (e: React.MouseEvent) => {
    e.preventDefault();
    setMenuOpen(false);
    navigate("/projects");
  };

  return (
    <header className="header">
      <div className="shell nav-wrap">
        <Brand />
        {isDashboard ? (
          <nav
            className="desktop-nav dashboard-nav"
            aria-label="Navigasi dashboard"
          >
            <a
              className="active"
              href="/dashboard"
              onClick={(e) => e.preventDefault()}
            >
              Dashboard
            </a>
            <a href="/projects" onClick={handleProjectsClick}>
              Proyek
            </a>
          </nav>
        ) : (
          <nav className="desktop-nav" aria-label="Navigasi utama">
            {navigation.map(([label, id]) => (
              <a
                className={activeNav === id ? "active" : ""}
                href={`#${id}`}
                key={id}
                onClick={(e) => {
                  e.preventDefault();
                  scrollTo(id);
                }}
              >
                {label}
              </a>
            ))}
          </nav>
        )}

        {!isDashboard && !loading && (
          <div className="nav-auth">
            {user ? (
              <a
                className="button primary nav-action"
                href="/dashboard"
                onClick={handleDashboardClick}
              >
                Dashboard
              </a>
            ) : (
              <>
                <Link
                  className="quick-demo-nav"
                  to={quickDemoPath}
                  aria-label="Simulasi Cepat, Coba tanpa masuk"
                >
                  <span className="quick-demo-nav-copy">
                    <strong>Simulasi Cepat</strong>
                    <small>Coba tanpa masuk</small>
                  </span>
                  <span className="quick-demo-nav-arrow" aria-hidden="true">
                    →
                  </span>
                </Link>
                <Link to="/login">Masuk</Link>
                <Link className="button primary nav-action" to="/register">
                  Daftar
                </Link>
              </>
            )}
          </div>
        )}

        <button
          className="menu-button"
          aria-label="Buka navigasi"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen(!menuOpen)}
        >
          <span />
          <span />
          <span />
        </button>
      </div>

      {menuOpen && (
        <nav className="mobile-nav" aria-label="Navigasi seluler">
          {isDashboard ? (
            <>
              <a
                className="active"
                href="/dashboard"
                onClick={(e) => {
                  e.preventDefault();
                  setMenuOpen(false);
                }}
              >
                Dashboard
              </a>
              <a href="/projects" onClick={handleProjectsClick}>
                Proyek
              </a>
            </>
          ) : (
            <>
              {navigation.map(([label, id]) => (
                <a
                  href={`#${id}`}
                  key={id}
                  onClick={(e) => {
                    e.preventDefault();
                    setMenuOpen(false);
                    scrollTo(id);
                  }}
                >
                  {label}
                </a>
              ))}
              <Link
                className="quick-demo-nav"
                to={quickDemoPath}
                onClick={() => setMenuOpen(false)}
                aria-label="Simulasi Cepat, Coba tanpa masuk"
              >
                <span className="quick-demo-nav-copy">
                  <strong>Simulasi Cepat</strong>
                  <small>Coba tanpa masuk</small>
                </span>
                <span className="quick-demo-nav-arrow" aria-hidden="true">
                  →
                </span>
              </Link>
              {user ? (
                <button
                  className="button primary"
                  onClick={handleDashboardClick}
                >
                  Dashboard
                </button>
              ) : (
                <>
                  <a
                    href="/login"
                    onClick={(event) => {
                      event.preventDefault();
                      setMenuOpen(false);
                      navigate("/login");
                    }}
                  >
                    Masuk
                  </a>
                  <a
                    href="/register"
                    onClick={(event) => {
                      event.preventDefault();
                      setMenuOpen(false);
                      navigate("/register");
                    }}
                  >
                    Daftar
                  </a>
                </>
              )}
            </>
          )}
        </nav>
      )}
    </header>
  );
}
