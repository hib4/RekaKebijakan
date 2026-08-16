import { useEffect, useMemo, useRef, useState } from "react";
import {
  getPublicQuickDemo,
  type ApiSimulationSnapshot,
} from "../../api/client";
import { demoCases } from "../../pages/SimulationWorkflow/workflowData";
import type {
  RiskNarrative,
  SimulationEvent,
} from "../../pages/SimulationWorkflow/workflowTypes";
import "./LandingSimulationPreview.css";

type DemoSource = "local" | "api";
type DemoStatus = "idle" | "running" | "complete";

type LandingDemoData = {
  title: string;
  question: string;
  personaCount: number;
  groupCount: number;
  rounds: number;
  platforms: string[];
  events: SimulationEvent[];
  risks: RiskNarrative[];
  finding: string;
};

const localDemo = demoCases["demo-mbg"];

function localDemoData(): LandingDemoData {
  return {
    title: localDemo.title,
    question: localDemo.question,
    personaCount: localDemo.personas.reduce(
      (total, persona) => total + persona.count,
      0,
    ),
    groupCount: localDemo.personas.length,
    rounds: 5,
    platforms: [...new Set(localDemo.events.map((event) => event.channel))],
    events: localDemo.events,
    risks: localDemo.risks,
    finding: localDemo.reportSections[0].content[0],
  };
}

function normalizeApiDemo(snapshot: ApiSimulationSnapshot): LandingDemoData | null {
  const rawEvents = snapshot.simulation?.events ?? [];
  const events = rawEvents
    .map((event, index): SimulationEvent | null => {
      const statement = event.statement ?? event.content;
      if (!statement) return null;
      return {
        id: event.id || `api-event-${index}`,
        round: event.round ?? 1,
        time: event.time ?? event.elapsed ?? "--:--",
        channel: event.channel ?? event.platform ?? "Kanal simulasi",
        persona: event.persona ?? event.persona_name ?? "Persona sintetis",
        group: event.group ?? "Stakeholder",
        type: event.type ?? event.event_type ?? "Respons",
        statement,
        stance: event.stance ?? "Netral",
        concerns: event.concerns ?? [],
        riskNarrative: event.risk_narrative ?? "Risiko kebijakan",
        influenceSource: event.influence_source ?? "Skenario kebijakan",
      };
    })
    .filter((event): event is SimulationEvent => event !== null);

  if (!events.length) return null;

  const people = snapshot.environment?.personas ?? [];
  const personaCount =
    snapshot.environment?.persona_count ??
    people.reduce((total, persona) => total + (persona.count ?? 1), 0);
  const configuredPlatforms =
    snapshot.environment?.config?.platforms ??
    snapshot.environment?.config?.channels ??
    [];
  const platforms = configuredPlatforms.length
    ? configuredPlatforms
    : [...new Set(events.map((event) => event.channel))];
  const risks = (snapshot.report?.risks ?? []).map(
    (risk, index): RiskNarrative => ({
      id: risk.id ?? `api-risk-${index}`,
      title: risk.title,
      level:
        risk.level === "low"
          ? "Rendah"
          : risk.level === "medium"
            ? "Sedang"
            : risk.level === "high"
              ? "Tinggi"
              : (risk.level ?? "Sedang"),
      trend:
        risk.trend === "decreasing"
          ? "Menurun"
          : risk.trend === "increasing"
            ? "Meningkat"
            : risk.trend === "stable"
              ? "Stabil"
              : (risk.trend ?? "Stabil"),
      evidence: risk.evidence ?? "Ditinjau dari event simulasi.",
    }),
  );
  const firstSection = snapshot.report?.sections?.[0];
  const sectionContent = firstSection?.paragraphs?.[0]
    ?? (Array.isArray(firstSection?.content)
      ? firstSection.content[0]
      : firstSection?.content)
    ?? firstSection?.content_markdown;

  return {
    title:
      snapshot.project?.name ??
      snapshot.project?.project_name ??
      localDemo.title,
    question:
      snapshot.project?.question ??
      snapshot.project?.objective ??
      localDemo.question,
    personaCount: personaCount || 30,
    groupCount: people.length || 6,
    rounds:
      snapshot.environment?.config?.rounds ??
      snapshot.environment?.config?.max_rounds ??
      5,
    platforms,
    events,
    risks: risks.length ? risks : localDemo.risks,
    finding: sectionContent || localDemo.reportSections[0].content[0],
  };
}

function representativeEvents(data: LandingDemoData) {
  const selected: SimulationEvent[] = [];
  for (let round = 1; round <= data.rounds; round += 1) {
    const event = data.events.find((item) => item.round === round);
    if (event) selected.push(event);
  }
  return selected.length ? selected.slice(0, 5) : data.events.slice(0, 5);
}

export function LandingSimulationPreview({
  onOpenWorkflow,
}: {
  onOpenWorkflow: () => void;
}) {
  const [data, setData] = useState<LandingDemoData>(localDemoData);
  const [source, setSource] = useState<DemoSource>("local");
  const [status, setStatus] = useState<DemoStatus>("idle");
  const [runData, setRunData] = useState<LandingDemoData | null>(null);
  const [visibleEventCount, setVisibleEventCount] = useState(0);
  const [currentRound, setCurrentRound] = useState(0);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const timerRef = useRef<number | null>(null);
  const startedRef = useRef(false);
  const activeData = runData ?? data;
  const runEvents = useMemo(
    () => representativeEvents(activeData),
    [activeData],
  );
  const visibleEvents = runEvents.slice(0, visibleEventCount);

  useEffect(() => {
    let cancelled = false;
    getPublicQuickDemo()
      .then((snapshot) => {
        const normalized = normalizeApiDemo(snapshot);
        if (!cancelled && !startedRef.current && normalized) {
          setData(normalized);
          setSource("api");
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(
    () => () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    },
    [],
  );

  const startDemo = () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    startedRef.current = true;
    const frozenData = data;
    const events = representativeEvents(frozenData);
    setRunData(frozenData);
    setEvidenceOpen(false);

    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setVisibleEventCount(events.length);
      setCurrentRound(frozenData.rounds);
      setStatus("complete");
      return;
    }

    setStatus("running");
    setVisibleEventCount(0);
    setCurrentRound(0);
    let nextIndex = 0;
    timerRef.current = window.setInterval(() => {
      const event = events[nextIndex];
      if (!event) {
        if (timerRef.current) window.clearInterval(timerRef.current);
        timerRef.current = null;
        setCurrentRound(frozenData.rounds);
        setStatus("complete");
        return;
      }
      nextIndex += 1;
      setVisibleEventCount(nextIndex);
      setCurrentRound(event.round);
      if (nextIndex >= events.length) {
        if (timerRef.current) window.clearInterval(timerRef.current);
        timerRef.current = null;
        setCurrentRound(frozenData.rounds);
        setStatus("complete");
      }
    }, 850);
  };

  const eventCountByPlatform = (platform: string) =>
    visibleEvents.filter(
      (event) =>
        event.channel.toLowerCase() === platform.toLowerCase() ||
        event.channel.toLowerCase().includes(platform.toLowerCase()),
    ).length;

  return (
    <div className="landing-demo-frame">
      <aside className="landing-demo-controls" aria-label="Kontrol demo simulasi">
        <div className="landing-demo-source">
          <span className={source} aria-hidden="true" />
          {source === "api" ? "Snapshot demo publik" : "Bundle demo lokal"}
        </div>
        <p className="label">SKENARIO KEBIJAKAN</p>
        <h3>{activeData.title}</h3>
        <p className="landing-demo-question">{activeData.question}</p>
        <dl className="landing-demo-config">
          <div><dt>Persona</dt><dd>{activeData.personaCount}</dd></div>
          <div><dt>Kelompok</dt><dd>{activeData.groupCount}</dd></div>
          <div><dt>Ronde</dt><dd>{activeData.rounds}</dd></div>
          <div><dt>Kanal</dt><dd>{activeData.platforms.length}</dd></div>
        </dl>
        <button
          className="button primary landing-demo-run"
          type="button"
          onClick={startDemo}
          disabled={status === "running"}
        >
          {status === "running"
            ? "Demo sedang berjalan"
            : status === "complete"
              ? "Jalankan ulang"
              : "Jalankan demo singkat"}
          <b>{status === "complete" ? "↻" : "→"}</b>
        </button>
        <p className="landing-demo-disclaimer">
          Eksplorasi persona sintetis, bukan prediksi opini publik.
        </p>
      </aside>

      <section className="landing-demo-results" aria-label="Hasil demo simulasi">
        <header className="landing-demo-results-header">
          <div>
            <p className="label">AKTIVITAS SIMULASI</p>
            <h3>
              {status === "idle"
                ? "Siap menjalankan skenario"
                : status === "running"
                  ? `Ronde ${Math.max(1, currentRound)} dari ${activeData.rounds}`
                  : "Demo selesai ditinjau"}
            </h3>
          </div>
          <span className={`landing-demo-status ${status}`} role="status" aria-live="polite">
            <i aria-hidden="true" />
            {status === "idle" ? "Siap" : status === "running" ? "Berjalan" : "Selesai"}
          </span>
        </header>

        <div
          className="landing-demo-rounds"
          aria-label={`Progres ${currentRound} dari ${activeData.rounds} ronde`}
        >
          {Array.from({ length: activeData.rounds }, (_, index) => index + 1).map(
            (round) => (
              <span className={round <= currentRound ? "done" : ""} key={round}>
                <i />
                Ronde {round}
              </span>
            ),
          )}
        </div>

        {status === "idle" ? (
          <div className="landing-demo-empty">
            <span aria-hidden="true">▶</span>
            <h4>Lihat bagaimana respons sintetis berkembang</h4>
            <p>
              Jalankan demo untuk mengikuti lima event representatif, risiko
              yang muncul, dan dasar temuan dari skenario MBG.
            </p>
          </div>
        ) : (
          <>
            <div className="landing-demo-channels" aria-label="Status kanal demo">
              {activeData.platforms.map((platform) => (
                <div key={platform}>
                  <span><i aria-hidden="true" />{platform}</span>
                  <b>{eventCountByPlatform(platform)} event</b>
                </div>
              ))}
            </div>
            <div className="landing-demo-feed" aria-live="polite">
              {visibleEvents.map((event) => (
                <article key={event.id}>
                  <div>
                    <span>Ronde {event.round}</span>
                    <span>{event.channel}</span>
                    <span>{event.type}</span>
                  </div>
                  <b>{event.persona} · {event.group}</b>
                  <p>{event.statement}</p>
                </article>
              ))}
            </div>
          </>
        )}

        {status === "complete" && (
          <div className="landing-demo-finding">
            <div className="landing-demo-finding-heading">
              <div>
                <p className="label">TEMUAN UTAMA</p>
                <p>{activeData.finding}</p>
              </div>
              <span>Risiko {activeData.risks[0]?.level ?? "Tinggi"}</span>
            </div>
            <div className="landing-demo-counts">
              <span><b>{activeData.personaCount}</b> persona</span>
              <span><b>{activeData.events.length}</b> total event</span>
              <span><b>{activeData.risks.length}</b> risiko utama</span>
            </div>
            <button
              className="landing-demo-evidence-toggle"
              type="button"
              aria-expanded={evidenceOpen}
              onClick={() => setEvidenceOpen((open) => !open)}
            >
              Lihat jejak bukti <b>{evidenceOpen ? "−" : "+"}</b>
            </button>
            {evidenceOpen && (
              <div className="landing-demo-evidence">
                {activeData.risks.map((risk) => (
                  <article key={risk.id}>
                    <div><b>{risk.title}</b><span>{risk.level} · {risk.trend}</span></div>
                    <p>{risk.evidence}</p>
                  </article>
                ))}
              </div>
            )}
            <button className="button secondary" type="button" onClick={onOpenWorkflow}>
              Lihat workflow lengkap <b>→</b>
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
