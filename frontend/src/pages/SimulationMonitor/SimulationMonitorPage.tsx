import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createInterview, sendRunInteraction } from "../../api/client";
import type { ApiEventDto, ApiInteractionMessageDto } from "../../api/client";
import { useControlRun, useRun, useRunEvents } from "../../api/queries";
import { AppShell } from "../../components/AppShell/AppShell";
import "./SimulationMonitor.css";

const toolOptions = [
  ["interview", "Wawancara persona", "Ajukan satu pertanyaan kepada kelompok sintetis."],
  ["report", "Tanya laporan", "Analisis hasil run dalam konteks laporan."],
  ["evidence", "Telusuri bukti", "Cari rantai sumber untuk sebuah temuan."],
  ["compare", "Bandingkan skenario", "Bandingkan hasil run dengan baseline."],
  ["revision", "Catatan revisi", "Susun perubahan kebijakan dari hasil run."],
] as const;

export default function SimulationMonitorPage() {
  const { runId = "" } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const runQuery = useRun(runId);
  const [cursor, setCursor] = useState<string>();
  const eventQuery = useRunEvents(runId, cursor);
  const control = useControlRun(runId);
  const [events, setEvents] = useState<ApiEventDto[]>([]);
  const [tool, setTool] = useState<(typeof toolOptions)[number][0]>("interview");
  const [question, setQuestion] = useState("");
  const [group, setGroup] = useState("");
  const [messages, setMessages] = useState<ApiInteractionMessageDto[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const eventIds = useRef(new Set<string>());

  useEffect(() => {
    const page = eventQuery.data;
    if (!page) return;
    const fresh = page.items.filter((event) => !eventIds.current.has(event.id));
    fresh.forEach((event) => eventIds.current.add(event.id));
    if (fresh.length) setEvents((current) => [...current, ...fresh]);
    if (page.next_cursor && page.next_cursor !== cursor) setCursor(page.next_cursor);
  }, [cursor, eventQuery.data]);

  const run = runQuery.data ?? eventQuery.data?.run;
  const changeStatus = async (action: "pause" | "resume" | "cancel") => {
    if (!run) return;
    try { await control.mutateAsync({ action, expectedVersion: run.version }); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Status run tidak dapat diperbarui."); }
  };
  const submit = async () => {
    if (!question.trim()) return;
    setSending(true); setError("");
    setMessages((items) => [...items, { id: `local-${Date.now()}`, role: "user", author: "Anda", tool, content: question }]);
    try {
      if (tool === "interview") {
        const interview = await createInterview(runId, { group: group || undefined, question });
        setMessages((items) => [...items, ...interview.answers]);
      } else {
        const answer = await sendRunInteraction(runId, { tool, question });
        setMessages((items) => [...items, answer]);
      }
      setQuestion("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Interaksi tidak dapat dikirim."); }
    finally { setSending(false); }
  };

  if (runQuery.isLoading) return <AppShell title="Memuat run" subtitle="Menghubungkan monitor ke event stream." eyebrow="Simulasi"><div className="project-skeleton"><span /><span /><span /></div></AppShell>;
  if (runQuery.isError || !run) return <AppShell title="Run tidak dapat dimuat" subtitle="Periksa koneksi atau akses run ini." eyebrow="Simulasi"><div className="state-block"><button className="button primary" onClick={() => runQuery.refetch()}>Muat ulang</button></div></AppShell>;

  const active = run.status === "running" || run.status === "queued";
  return <AppShell title="Simulation Monitor" subtitle="Pantau event server secara langsung dan gunakan alat interaksi sesuai konteksnya." eyebrow="Workspace kebijakan" actions={<><button className="button primary" disabled={control.isPending || ["cancelled", "failed", "completed"].includes(run.status)} onClick={() => changeStatus(active ? "pause" : "resume")}>{active ? "Jeda simulasi" : "Lanjutkan simulasi"}</button><button className="button danger" disabled={control.isPending || ["cancelled", "failed", "completed"].includes(run.status)} onClick={() => changeStatus("cancel")}>Batalkan run</button><button className="button secondary" onClick={() => navigate(`/projects/${run.project_id}`)}>Kembali ke workspace</button></>}>
    {error && <div className="inline-alert error" role="alert"><p>{error}</p></div>}
    <section className="experiment-controls" aria-label="Status run"><span className={`project-badge monitor-status ${run.status}`}><i />{run.status}</span><span>Ronde {run.current_round} dari {run.total_rounds}</span><span>{run.event_count} event</span><span>Cursor {cursor ?? "awal"}</span></section>
    <section className="experiment-canvas" aria-labelledby="run-title"><header><div><p className="eyebrow">RUN AKTIF</p><h2 id="run-title">Skenario {run.scenario_id}</h2></div><span className="round-badge">{run.progress}%</span></header><div className="progress-bar" aria-label={`Progres ${run.progress} persen`}><span style={{ width: `${run.progress}%` }} /></div><div className="detail-panel"><div className="detail-heading"><h2>Event simulasi</h2><span>{events.length} event diterima</span></div>{events.length === 0 ? <p className="empty-copy">Menunggu event dari run.</p> : events.toReversed().map((event) => <article className="event-row" key={event.id}><span>Ronde {event.round ?? "-"} · {event.time ?? event.elapsed ?? ""}</span><b>{event.persona_name ?? event.persona ?? "Persona"} · {event.event_type ?? event.type ?? "Event"}</b><p>{event.content ?? event.statement}</p>{event.risk_narrative && <i className="risk-tag sedang">{event.risk_narrative}</i>}</article>)}</div></section>
    <section className="experiment-details" aria-label="Alat interaksi"><div className="monitor-tabs" role="tablist">{toolOptions.map(([id, label]) => <button key={id} aria-selected={tool === id} onClick={() => setTool(id)}>{label}</button>)}</div><div className="detail-panel"><div className="detail-heading"><div><h2>{toolOptions.find(([id]) => id === tool)?.[1]}</h2><p>{toolOptions.find(([id]) => id === tool)?.[2]}</p></div></div>{tool === "interview" && <label className="field">Kelompok persona<input value={group} onChange={(event) => setGroup(event.target.value)} placeholder="Opsional, mis. Pelaku UMKM mikro" /></label>}<div className="chat-messages" aria-live="polite">{messages.filter((message) => message.tool === tool || tool === "interview").map((message) => <p key={message.id} className={message.role === "user" ? "user" : "agent"}><b>{message.author ?? (message.role === "user" ? "Anda" : "Agent")}</b>{message.content ?? message.text}</p>)}</div><form onSubmit={(event) => { event.preventDefault(); submit(); }}><label className="field">Pertanyaan<textarea rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} /></label><button className="button primary" disabled={sending || !question.trim()}>{sending ? "Mengirim..." : "Kirim"}</button></form></div></section>
    <p className="responsible-note">Event dan jawaban berasal dari persona sintetis serta sumber run. Hasil merupakan dukungan analisis, bukan kesimpulan opini masyarakat.</p>
  </AppShell>;
}
