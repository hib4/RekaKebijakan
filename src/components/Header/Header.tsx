import { useState, useEffect } from "react";
import { navigation } from "../../data/content";
import "./Header.css";

const scrollTo = (id: string) => {
  const element = document.getElementById(id);
  if (element) {
    element.scrollIntoView({ behavior: "smooth" });
  }
};

export function Brand() {
  return (
    <a
      className="brand"
      href="/"
      aria-label="RekaKebijakan, kembali ke awal"
      onClick={(e) => {
        e.preventDefault();
        window.history.pushState(null, "", "/");
        window.dispatchEvent(new PopStateEvent("popstate"));
        scrollTo("utama");
      }}
    >
      <span aria-hidden="true">RK</span>
      <b>RekaKebijakan</b>
    </a>
  );
}

interface HeaderProps {
  isDashboard?: boolean;
}

export default function Header({ isDashboard = false }: HeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeNav, setActiveNav] = useState("");

  useEffect(() => {
    if (isDashboard) return;

    const sections = [
      document.getElementById("hero"),
      ...navigation.map(([, id]) => document.getElementById(id))
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
      { rootMargin: "-35% 0px -55% 0px" }
    );

    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [isDashboard]);

  const handleDashboardClick = (e: React.MouseEvent) => {
    e.preventDefault();
    setMenuOpen(false);
    window.history.pushState(null, "", "/dashboard");
    window.dispatchEvent(new PopStateEvent("popstate"));
  };

  const handleProjectsClick = (e: React.MouseEvent) => {
    e.preventDefault();
    setMenuOpen(false);
    window.history.pushState(null, "", "/projects");
    window.dispatchEvent(new PopStateEvent("popstate"));
  };

  return (
    <header className="header">
      <div className="shell nav-wrap">
        <Brand />
        {isDashboard ? (
          <nav className="desktop-nav dashboard-nav" aria-label="Navigasi dashboard">
            <a className="active" href="/dashboard" onClick={(e) => e.preventDefault()}>
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

        {!isDashboard && (
          <button className="button primary nav-action" onClick={handleDashboardClick}>
            Dashboard
          </button>
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
              <a className="active" href="/dashboard" onClick={(e) => { e.preventDefault(); setMenuOpen(false); }}>
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
              <button className="button primary" onClick={handleDashboardClick}>
                Dashboard
              </button>
            </>
          )}
        </nav>
      )}
    </header>
  );
}
