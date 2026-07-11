import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { navigation, problems, processSteps } from "./data/content";
import type { Scenario } from "./data/scenarios";
import { scenarios } from "./data/scenarios";
import "./App.css";

const scrollTo = (id: string) =>
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
const rounds = [1, 2, 3, 4, 5];
const audienceGroups = [
  [
    "01",
    "Unit analisis kebijakan",
    "Membandingkan rancangan, asumsi dampak, dan pertanyaan konsultasi.",
  ],
  [
    "02",
    "Pemerintah daerah",
    "Meninjau respons layanan publik, UMKM, komunitas lokal, dan kelompok rentan.",
  ],
  [
    "03",
    "Peneliti dan kampus",
    "Menguji hipotesis kebijakan dengan skenario yang dapat ditelusuri.",
  ],
  [
    "04",
    "Organisasi masyarakat",
    "Mengidentifikasi risiko narasi dan kelompok yang perlu dilibatkan lebih awal.",
  ],
];

type SimulationMetrics = {
  support: number;
  concern: number;
  risk: Scenario["risk"];
  insight: string;
  personas: number;
  evidence: number;
  narratives: number;
};

const interpolate = (start: number, end: number, round: number) =>
  Math.round(start + ((end - start) * (round - 1)) / 4);

function getRoundMetrics(scenario: Scenario, round: number): SimulationMetrics {
  const supportStart = Math.max(18, scenario.support - 24);
  const concernStart = Math.min(62, scenario.concern + 18);
  const personasStart = scenario.personas + 6;
  const evidenceStart = Math.max(2, scenario.evidence - 3);
  const narrativesStart = scenario.narratives + 2;
  const risk =
    scenario.risk === "Rendah" && round < 4
      ? "Sedang"
      : scenario.risk === "Sedang" && round < 3
        ? "Tinggi"
        : scenario.risk;

  return {
    support: interpolate(supportStart, scenario.support, round),
    concern: interpolate(concernStart, scenario.concern, round),
    risk,
    insight:
      round < 5
        ? "Ronde simulasi sedang mengumpulkan respons persona dan menguji konsistensi narasi."
        : scenario.insight,
    personas: interpolate(personasStart, scenario.personas, round),
    evidence: interpolate(evidenceStart, scenario.evidence, round),
    narratives: interpolate(narrativesStart, scenario.narratives, round),
  };
}

function Brand() {
  return (
    <a
      className="brand"
      href="#utama"
      aria-label="RekaKebijakan, kembali ke awal"
    >
      <span aria-hidden="true">RK</span>
      <b>RekaKebijakan</b>
    </a>
  );
}

const activeExperiments = [
  {
    name: "Registrasi Digital UMKM",
    scenario: scenarios[2],
    nodes: ["Pelaku mikro", "Dinas UMKM", "Pendamping", "Pasar"],
  },
  {
    name: "Standardisasi Bengkel",
    scenario: scenarios[1],
    nodes: ["Pemilik bengkel", "Teknisi", "KLHK", "Asosiasi"],
  },
  {
    name: "Penyaluran Pupuk",
    scenario: scenarios[0],
    nodes: ["Petani", "Kios Resmi", "Distributor", "Kementerian"],
  },
];

function ProductPreview() {
  const [activeExpIndex, setActiveExpIndex] = useState(0);
  const [previewRound, setPreviewRound] = useState(() =>
    window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 5 : 1,
  );
  const activeExp = activeExperiments[activeExpIndex];
  const previewMetrics = getRoundMetrics(activeExp.scenario, previewRound);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return undefined;
    }

    let timerId: number;

    const runNextTick = (currentRound: number) => {
      const isEnd = currentRound >= 5;
      const delay = 1200;

      timerId = window.setTimeout(() => {
        if (isEnd) {
          setActiveExpIndex((prevIdx) => (prevIdx + 1) % activeExperiments.length);
          setPreviewRound(1);
          runNextTick(1);
        } else {
          setPreviewRound(currentRound + 1);
          runNextTick(currentRound + 1);
        }
      }, delay);
    };

    runNextTick(previewRound);

    return () => window.clearTimeout(timerId);
  }, []);

  return (
    <div
      className="product-preview"
      aria-label={`Pratinjau simulasi ${activeExp.name}`}
    >
      <div className="preview-top">
        <div>
          <small>EKSPERIMEN AKTIF</small>
          <strong>{activeExp.name}</strong>
        </div>
        <span className="round-tag">Ronde {previewRound} dari 5</span>
      </div>
      <div className="network" aria-hidden="true">
        <svg viewBox="0 0 520 218" preserveAspectRatio="none">
          <path d="M55 106 L158 58 L270 112 L390 57 M158 58 L191 168 L270 112 L415 166 M270 112 L470 106" />
          <circle className={previewRound >= 1 ? "active-node" : ""} cx="55" cy="106" r="9" />
          <circle className={previewRound >= 2 ? "active-node" : ""} cx="158" cy="58" r="11" />
          <circle className={previewRound >= 2 ? "active-node" : ""} cx="191" cy="168" r="9" />
          <circle className={previewRound >= 3 ? "active-node primary-node" : ""} cx="270" cy="112" r="15" />
          <circle className={previewRound >= 4 ? "active-node" : ""} cx="390" cy="57" r="10" />
          <circle className={previewRound >= 5 ? "active-node" : ""} cx="415" cy="166" r="10" />
          <circle className={previewRound >= 5 ? "active-node" : ""} cx="470" cy="106" r="9" />
        </svg>
        <span className="node n1">{activeExp.nodes[0]}</span>
        <span className="node n2">{activeExp.nodes[1]}</span>
        <span className="node n3">{activeExp.nodes[2]}</span>
        <span className="node n4">{activeExp.nodes[3]}</span>
      </div>
      <div className="preview-rounds" aria-hidden="true">
        {rounds.map((item) => (
          <i className={item <= previewRound ? "done" : ""} key={item}>
            {item}
          </i>
        ))}
      </div>
      <div className="preview-metrics">
        <div>
          <small>Dukungan</small>
          <b>{previewMetrics.support}%</b>
          <i className="meter blue">
            <em style={{ width: `${previewMetrics.support}%` }} />
          </i>
        </div>
        <div>
          <small>Kekhawatiran</small>
          <b>{previewMetrics.concern}%</b>
          <i className="meter amber">
            <em style={{ width: `${previewMetrics.concern}%` }} />
          </i>
        </div>
        <div>
          <small>Risiko narasi</small>
          <b>{previewMetrics.risk}</b>
          <span className="status-line">{previewRound === 5 ? "Terkendali" : "Dalam evaluasi"}</span>
        </div>
      </div>
      <div className="activity">
        <span /> {previewRound === 5 ? "Aktivitas ronde selesai ditinjau" : "Persona sedang merespons skenario"}
      </div>
    </div>
  );
}

function ContactDialog({ onClose }: { onClose: () => void }) {
  const [sent, setSent] = useState(false);
  const titleId = useId();
  useEffect(() => {
    const close = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSent(true);
  };
  return (
    <div className="dialog-backdrop" onMouseDown={onClose}>
      <section
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <button
          className="dialog-close"
          onClick={onClose}
          aria-label="Tutup dialog"
        >
          X
        </button>
        {sent ? (
          <div className="form-success">
            <p className="eyebrow">PERMINTAAN TERCATAT</p>
            <h2 id={titleId}>Terima kasih.</h2>
            <p>
              Ini adalah interaksi prototipe. Informasi tidak dikirim atau
              disimpan.
            </p>
            <button className="button primary" onClick={onClose}>
              Tutup
            </button>
          </div>
        ) : (
          <>
            <p className="eyebrow">DISKUSI PILOT</p>
            <h2 id={titleId}>Ceritakan kebutuhan institusi Anda.</h2>
            <form onSubmit={submit}>
              <label>
                Nama
                <input required name="name" autoFocus />
              </label>
              <label>
                Institusi
                <input required name="organization" />
              </label>
              <label>
                Email
                <input required name="email" type="email" />
              </label>
              <label>
                Tujuan penggunaan
                <textarea required name="use" rows={3} />
              </label>
              <button className="button primary" type="submit">
                Kirim permintaan
              </button>
            </form>
          </>
        )}
      </section>
    </div>
  );
}

function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeNav, setActiveNav] = useState("");
  const [activeStep, setActiveStep] = useState(0);
  const [caraKerjaVisible, setCaraKerjaVisible] = useState(false);
  const [scenarioIndex, setScenarioIndex] = useState(0);
  const [round, setRound] = useState(1);
  const [hasRun, setHasRun] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const simulationTimer = useRef<number | null>(null);
  const scenario = scenarios[scenarioIndex];
  const metrics = useMemo(
    () => getRoundMetrics(scenario, round),
    [scenario, round],
  );
  useEffect(() => {
    const element = document.getElementById("cara-kerja");
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setCaraKerjaVisible(true);
        }
      },
      { threshold: 0.1 }
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const sections = [...navigation]
      .map(([, id]) => document.getElementById(id))
      .filter(Boolean) as HTMLElement[];
    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach(
          (entry) => entry.isIntersecting && setActiveNav(entry.target.id),
        ),
      { rootMargin: "-35% 0px -55% 0px" },
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);
  useEffect(
    () => () => {
      if (simulationTimer.current)
        window.clearInterval(simulationTimer.current);
    },
    [],
  );
  useEffect(() => {
    if (!caraKerjaVisible || activeStep >= processSteps.length - 1) {
      return;
    }
    const timer = window.setInterval(() => {
      setActiveStep((prev) => prev + 1);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeStep, caraKerjaVisible]);
  const stopSimulationTimer = () => {
    if (simulationTimer.current) {
      window.clearInterval(simulationTimer.current);
      simulationTimer.current = null;
    }
  };
  const chooseScenario = (index: number) => {
    stopSimulationTimer();
    setScenarioIndex(index);
    setHasRun(false);
    setIsRunning(false);
    setRound(1);
    setEvidenceOpen(false);
  };
  const updateRound = (value: number) => {
    stopSimulationTimer();
    setRound(value);
    setHasRun(false);
    setIsRunning(false);
  };
  const runSimulation = () => {
    stopSimulationTimer();
    setHasRun(false);
    setIsRunning(true);
    setEvidenceOpen(false);

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setRound(5);
      setIsRunning(false);
      setHasRun(true);
      return;
    }

    setRound(1);
    simulationTimer.current = window.setInterval(() => {
      setRound((currentRound) => {
        if (currentRound >= 4) {
          stopSimulationTimer();
          setIsRunning(false);
          setHasRun(true);
          return 5;
        }

        return currentRound + 1;
      });
    }, 1000);
  };
  return (
    <div id="utama">
      <header className="header">
        <div className="shell nav-wrap">
          <Brand />
          <nav className="desktop-nav" aria-label="Navigasi utama">
            {navigation.map(([label, id]) => (
              <a
                className={activeNav === id ? "active" : ""}
                href={`#${id}`}
                key={id}
              >
                {label}
              </a>
            ))}
          </nav>
          <button
            className="button primary nav-action"
            onClick={() => scrollTo("simulasi")}
          >
            Lihat Simulasi
          </button>
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
            {navigation.map(([label, id]) => (
              <a href={`#${id}`} key={id} onClick={() => setMenuOpen(false)}>
                {label}
              </a>
            ))}
            <button
              className="button primary"
              onClick={() => {
                setMenuOpen(false);
                scrollTo("simulasi");
              }}
            >
              Lihat Simulasi
            </button>
          </nav>
        )}
      </header>
      <main>
        <section className="hero section" aria-labelledby="hero-title">
          <div className="shell hero-grid">
            <div>
              <p className="eyebrow">
                KEBIJAKAN YANG LEBIH SIAP SEBELUM DITERAPKAN
              </p>
              <h1 id="hero-title">
                Uji dampak.
                <br />
                Temukan risiko.
                <br />
                <span>Putuskan lebih baik.</span>
              </h1>
              <p className="lead">
                RekaKebijakan membantu perancang kebijakan menguji respons
                kelompok masyarakat, menelusuri narasi berisiko, dan
                membandingkan skenario sebelum konsultasi publik.
              </p>
              <div className="actions">
                <button
                  className="button primary"
                  onClick={() => scrollTo("simulasi")}
                >
                  Coba simulasi interaktif <b>→</b>
                </button>
                <button
                  className="button secondary"
                  onClick={() => scrollTo("cara-kerja")}
                >
                  Pelajari cara kerja
                </button>
              </div>
              <p className="responsibility">
                Pendukung keputusan, bukan pengganti partisipasi masyarakat.
              </p>
            </div>
            <ProductPreview />
          </div>
        </section>
        <section className="audience" aria-labelledby="audience-title">
          <div className="shell audience-grid">
            <div className="audience-intro">
              <p className="eyebrow">DIRANCANG UNTUK</p>
              <h2 id="audience-title">
                Institusi yang perlu menguji kebijakan sebelum konsultasi
                publik.
              </h2>
            </div>
            <div className="audience-list">
              {audienceGroups.map(([num, title, text]) => (
                <article key={num}>
                  <span>{num}</span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
        <section className="section" id="tentang">
          <div className="shell">
            <p className="eyebrow">01 / PERMASALAHAN</p>
            <h2 className="display">
              Kebijakan yang baik dapat gagal karena risiko yang terlambat
              terlihat.
            </h2>
            <div className="problem-grid problem-grid-compact">
              {problems.map(([num, title, text]) => (
                <article className="problem" key={num}>
                  <span>{num}</span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
        <section className="inverse section" id="cara-kerja">
          <div className="shell">
            <p className="eyebrow">02 / CARA KERJA</p>
            <h2 className="display">
              Dari rancangan menjadi eksperimen yang dapat ditelusuri.
            </h2>
            <p className="inverse-intro">
              Empat langkah terstruktur untuk mengubah asumsi menjadi temuan
              yang dapat diperiksa dan dibandingkan.
            </p>
            <div className="step-grid">
              {processSteps.map(([num, title, text], index) => (
                <button
                  className={`step ${activeStep === index ? "active" : ""}`}
                  key={num}
                  onMouseEnter={() => setActiveStep(index)}
                  onFocus={() => setActiveStep(index)}
                  onClick={() => setActiveStep(index)}
                >
                  <span>{num}</span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </button>
              ))}
            </div>
          </div>
        </section>
        <section
          className="section simulation"
          id="simulasi"
          aria-labelledby="sim-title"
        >
          <div className="shell">
            <p className="eyebrow">03 / SIMULASI INTERAKTIF</p>
            <h2 id="sim-title" className="display">
              Ubah skenario. Lihat bagaimana hasilnya bergerak.
            </h2>
            <p className="section-description">
              Contoh ini menggunakan data demonstrasi. Pilih intervensi dan
              jalankan ronde untuk melihat perubahan dukungan, kekhawatiran,
              serta risiko narasi.
            </p>
            <p className="demo-note">
              Data pada bagian ini merupakan data demonstrasi.
            </p>
            <div className="simulation-grid">
              <section
                className="simulation-controls"
                aria-label="Kontrol simulasi"
              >
                <p className="label">SKENARIO KEBIJAKAN</p>
                <div className="scenario-list">
                  {scenarios.map((item, index) => (
                    <button
                      className={scenarioIndex === index ? "selected" : ""}
                      key={item.id}
                      onClick={() => chooseScenario(index)}
                    >
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      {item.name}
                    </button>
                  ))}
                </div>
                <label className="round-control" htmlFor="round">
                  <span>RONDE SIMULASI</span>
                  <b>{round} dari 5</b>
                  <input
                    id="round"
                    type="range"
                    min="1"
                    max="5"
                    value={round}
                    onChange={(event) =>
                      updateRound(Number(event.target.value))
                    }
                  />
                  <small>Atur ronde untuk meninjau progres eksperimen.</small>
                </label>
                <button
                  className="button primary run"
                  onClick={runSimulation}
                  disabled={isRunning}
                >
                  {isRunning ? "Simulasi berjalan" : "Jalankan simulasi"}{" "}
                  <b>→</b>
                </button>
              </section>
              <section
                className="simulation-results"
                aria-label="Hasil simulasi"
              >
                <div className="result-heading">
                  <div>
                    <p className="label">HASIL SKENARIO</p>
                    <h3>{scenario.name}</h3>
                  </div>
                  <span className={`risk risk-${metrics.risk.toLowerCase()}`}>
                    Risiko {metrics.risk}
                  </span>
                </div>
                <div className="result-bars">
                  <div>
                    <div>
                      <span>Dukungan</span>
                      <b>{metrics.support}%</b>
                    </div>
                    <div className="bar">
                      <i
                        className="support"
                        style={{ width: `${metrics.support}%` }}
                      />
                    </div>
                  </div>
                  <div>
                    <div>
                      <span>Kekhawatiran</span>
                      <b>{metrics.concern}%</b>
                    </div>
                    <div className="bar">
                      <i
                        className="concern"
                        style={{ width: `${metrics.concern}%` }}
                      />
                    </div>
                  </div>
                </div>
                <div className="result-progress">
                  <span>Ronde saat ini</span>
                  <div>
                    {rounds.map((item) => (
                      <i className={item <= round ? "done" : ""} key={item}>
                        {item}
                      </i>
                    ))}
                  </div>
                  <b>
                    {isRunning
                      ? "Simulasi sedang berjalan"
                      : hasRun
                        ? "Eksperimen selesai"
                        : "Menunggu simulasi"}
                  </b>
                </div>
                <article className="insight">
                  <p className="label">TEMUAN UTAMA</p>
                  <p>{metrics.insight}</p>
                </article>
                <div className="result-counts">
                  <div>
                    <b>{metrics.personas}</b>
                    <span>Persona terdampak</span>
                  </div>
                  <div>
                    <b>{metrics.evidence}</b>
                    <span>Bukti tertaut</span>
                  </div>
                  <div>
                    <b>{metrics.narratives}</b>
                    <span>Narasi terdeteksi</span>
                  </div>
                </div>
                <button
                  className="text-button"
                  onClick={() => setEvidenceOpen(!evidenceOpen)}
                  aria-expanded={evidenceOpen}
                >
                  Lihat dasar temuan <b>{evidenceOpen ? "−" : "+"}</b>
                </button>
                {evidenceOpen && (
                  <div className="evidence-panel">
                    <p className="label">JEJAK TEMUAN</p>
                    <div>
                      <b>Pasal 7 ayat (2)</b>
                      <span>
                        Pendaftaran tidak dikenakan biaya selama masa transisi.
                      </span>
                    </div>
                    <div>
                      <b>Catatan persona</b>
                      <span>
                        Kelompok berliterasi digital rendah meminta pendampingan
                        tatap muka.
                      </span>
                    </div>
                  </div>
                )}
                <p className="sr-only" aria-live="polite">
                  Skenario {scenario.name}, ronde {round}. Dukungan{" "}
                  {metrics.support} persen, kekhawatiran {metrics.concern}{" "}
                  persen, risiko narasi {metrics.risk}.
                </p>
              </section>
            </div>
          </div>
        </section>
        <section className="surface section" id="keunggulan">
          <div className="shell">
            <p className="eyebrow">04 / KEUNGGULAN</p>
            <h2 className="display">
              Bukan kotak hitam. Setiap temuan memiliki jejak.
            </h2>
            <p className="section-description">
              Model bahasa membantu persona mengambil keputusan. Aturan
              simulasi, validasi, perubahan sikap, dan agregasi tetap
              dikendalikan oleh sistem yang dapat diperiksa.
            </p>
            <div className="advantages">
              <article className="advantage feature-main">
                <p className="eyebrow">BERORIENTASI PADA BUKTI</p>
                <h3>Temuan yang dapat ditelusuri.</h3>
                <p>
                  Temuan faktual ditautkan ke pasal, data, atau peristiwa
                  simulasi. Opini dan prediksi diberi label yang jelas.
                </p>
                <div className="source-card">
                  <small>SUMBER TEMUAN</small>
                  <b>Pasal 7 ayat (2)</b>
                  <q>Pendaftaran tidak dikenakan biaya selama masa transisi.</q>
                  <span>Bukti terverifikasi</span>
                </div>
              </article>
              <article className="advantage">
                <h3>Dapat direproduksi</h3>
                <p>
                  Versi dokumen, persona, prompt, model, graf, dan random seed
                  dibekukan pada setiap eksperimen.
                </p>
              </article>
              <article className="advantage">
                <h3>Biaya terkendali</h3>
                <p>
                  Model berbiaya rendah menangani giliran persona. Model yang
                  lebih kuat hanya digunakan ketika dampaknya berarti.
                </p>
              </article>
            </div>
          </div>
        </section>
        <section className="inverse section" id="dampak">
          <div className="shell">
            <p className="eyebrow">05 / DAMPAK</p>
            <h2 className="display">
              Menyiapkan partisipasi publik yang lebih terarah.
            </h2>
            <p className="inverse-intro">
              RekaKebijakan membantu institusi menemukan hal yang belum diuji,
              bukan menggantikan warga yang perlu didengar.
            </p>
            <div className="impact-grid">
              <div>
                <b>90%</b>
                <p>Target temuan faktual memiliki bukti</p>
              </div>
              <div>
                <b>20-50</b>
                <p>Persona sintetis per simulasi</p>
              </div>
              <div>
                <b>3 mode</b>
                <p>Eksekusi untuk ketahanan sistem</p>
              </div>
              <div>
                <b>SDG 16</b>
                <p>Institusi efektif, akuntabel, dan inklusif</p>
              </div>
            </div>
            <p className="impact-note">
              Target produk dan karakteristik sistem, bukan statistik dampak
              yang telah diverifikasi secara independen.
            </p>
          </div>
        </section>
        <section className="section" id="batas">
          <div className="shell">
            <p className="eyebrow">06 / BATAS PENGGUNAAN</p>
            <h2 className="display">
              Simulasi mendukung keputusan. Manusia tetap menentukan.
            </h2>
            <div className="use-grid">
              <article>
                <h3>RekaKebijakan dapat</h3>
                {[
                  "Menemukan asumsi yang belum diuji",
                  "Mengidentifikasi kelompok terdampak",
                  "Membandingkan skenario kebijakan",
                  "Menelusuri narasi dan bukti",
                  "Menyiapkan konsultasi publik",
                ].map((text) => (
                  <p key={text}>
                    <b aria-hidden="true">+</b>
                    {text}
                  </p>
                ))}
              </article>
              <article>
                <h3>RekaKebijakan tidak dapat</h3>
                {[
                  "Mewakili seluruh masyarakat",
                  "Menggantikan konsultasi publik",
                  "Menentukan kebijakan secara otomatis",
                  "Memprediksi perilaku warga secara pasti",
                  "Digunakan untuk menargetkan individu",
                ].map((text) => (
                  <p key={text}>
                    <b aria-hidden="true">−</b>
                    {text}
                  </p>
                ))}
              </article>
            </div>
          </div>
        </section>
        <section className="cta">
          <div className="shell">
            <p className="eyebrow">MULAI DARI PERTANYAAN YANG BELUM TERJAWAB</p>
            <h2>Uji kebijakan sebelum dampaknya menjadi kenyataan.</h2>
            <p>
              Bangun skenario, temukan risiko, dan siapkan konsultasi publik
              dengan dasar yang lebih kuat.
            </p>
            <div className="actions">
              <button
                className="button white"
                onClick={() => scrollTo("simulasi")}
              >
                Coba simulasi <b>→</b>
              </button>
              <button
                className="button outline-white"
                onClick={() => setDialogOpen(true)}
              >
                Diskusikan pilot project
              </button>
            </div>
          </div>
        </section>
      </main>
      <footer>
        <div className="shell footer-grid">
          <div>
            <Brand />
            <p>
              Simulasi kebijakan yang transparan, terukur, dan bertanggung
              jawab.
            </p>
          </div>
          <div>
            <small>PRODUK</small>
            <a href="#cara-kerja">Cara kerja</a>
            <a href="#simulasi">Simulasi</a>
            <a href="#keunggulan">Keunggulan</a>
          </div>
          <div>
            <small>PENGGUNAAN BERTANGGUNG JAWAB</small>
            <a href="#batas">Batas penggunaan</a>
            <a href="#tentang">Tentang simulasi</a>
          </div>
          <div>
            <small>GEMASTIK 2026</small>
            <p>
              Divisi VIII
              <br />
              Pengembangan Perangkat Lunak
            </p>
          </div>
        </div>
        <div className="shell copyright">
          © 2026 RekaKebijakan.
        </div>
      </footer>
      {dialogOpen && <ContactDialog onClose={() => setDialogOpen(false)} />}
    </div>
  );
}

export default App;
