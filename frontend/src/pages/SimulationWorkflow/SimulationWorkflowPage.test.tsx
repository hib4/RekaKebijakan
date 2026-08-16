import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { delay, http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "../../test/server";
import { AuthContext } from "../../auth/auth-context";
import type { ApiSimulationSnapshot } from "../../api/client";
import SimulationWorkflowPage from "./SimulationWorkflowPage";
import { createWorkflowSession, quickPresentationSessionKey } from "./workflowSession";

const auth = {
  user: { id: "user-1", name: "Analis", email: "analis@example.com" },
  loading: false,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
};

function snapshot(currentStage: "graph" | "environment" | "simulation" | "report" | "interaction" = "report"): ApiSimulationSnapshot {
  return {
    project: { name: "Program Backend", question: "Apa dampak program?" },
    current_stage: currentStage,
    stages: {
      graph: { status: currentStage === "graph" ? "ready" : "completed", progress: currentStage === "graph" ? 0 : 100 },
      environment: { status: currentStage === "graph" ? "locked" : "completed", progress: currentStage === "graph" ? 0 : 100 },
      simulation: { status: currentStage === "simulation" ? "processing" : currentStage === "graph" ? "locked" : "completed", progress: currentStage === "simulation" ? 40 : currentStage === "graph" ? 0 : 100 },
      report: { status: currentStage === "report" ? "completed" : currentStage === "interaction" ? "completed" : "locked", progress: currentStage === "report" || currentStage === "interaction" ? 100 : 0 },
      interaction: { status: currentStage === "interaction" || currentStage === "report" ? "ready" : "locked", progress: 0 },
    },
    graph: { nodes: [], edges: [] },
    environment: { personas: [], persona_count: 0, config: { rounds: 5 } },
    simulation: { status: currentStage === "simulation" ? "running" : currentStage === "graph" ? "ready" : "completed", events: [] },
    report: {
      status: currentStage === "report" || currentStage === "interaction" ? "completed" : "locked",
      progress: currentStage === "report" || currentStage === "interaction" ? 100 : 0,
      sections: [{ id: "summary", title: "Ringkasan", paragraphs: ["Temuan backend."] }],
      risks: [],
    },
    logs: [],
  };
}

function embeddedRuntimeGraph(): NonNullable<ApiSimulationSnapshot["runtime_graph"]> {
  return {
    graph_id: "runtime-quick-demo",
    graph_kind: "runtime",
    source_revision: 1,
    mapping_status: "completed",
    node_count: 2,
    edge_count: 1,
    nodes: [
      { id: "runtime-a", label: "Persona A", type: "Persona" },
      { id: "runtime-b", label: "Isu B", type: "PolicyIssue" },
    ],
    edges: [
      { id: "runtime-edge", source: "runtime-a", target: "runtime-b", type: "LINKS_TO" },
    ],
  };
}

function saveQuickGraphPresentation(simulationId: string) {
  const presentation = createWorkflowSession(simulationId, "Registrasi Digital UMKM");
  presentation.currentStep = 2;
  presentation.viewMode = "graph";
  presentation.steps[1] = { status: "completed", progress: 100, activeTask: null };
  presentation.steps[2] = { status: "ready", progress: 0, activeTask: null };
  sessionStorage.setItem(
    quickPresentationSessionKey(simulationId),
    JSON.stringify({ version: 2, session: presentation }),
  );
}

function renderWorkflow(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AuthContext value={auth}>
        <Routes>
          <Route path="/simulation/:simulationId" element={<SimulationWorkflowPage />} />
        </Routes>
      </AuthContext>
    </MemoryRouter>,
  );
}

describe("SimulationWorkflowPage live mode", () => {
  beforeEach(() => {
    sessionStorage.clear();
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
    });
    Object.defineProperties(SVGSVGElement.prototype, {
      width: { configurable: true, value: { baseVal: { value: 820 } } },
      height: { configurable: true, value: { baseVal: { value: 440 } } },
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("loads a non-demo ID only from the backend without local initialization", async () => {
    const storageRead = vi.spyOn(Storage.prototype, "getItem");
    const storageWrite = vi.spyOn(Storage.prototype, "setItem");
    server.use(
      http.get("/backend/api/simulations/live-123", () => HttpResponse.json({
        project: { name: "Program Backend", question: "Apa dampak program?" },
        current_stage: "graph",
        stages: { graph: { status: "ready", progress: 0 } },
        graph: { nodes: [], edges: [] },
        environment: { personas: [], persona_count: 0, config: { rounds: 5 } },
        simulation: { status: "ready", events: [] },
        report: { sections: [], risks: [] },
        logs: [],
      })),
    );

    renderWorkflow("/simulation/live-123");

    expect(await screen.findByRole("heading", { name: "Program Backend" })).toBeInTheDocument();
    expect(screen.queryByText("Registrasi Digital UMKM")).not.toBeInTheDocument();
    expect(storageRead).not.toHaveBeenCalled();
    expect(storageWrite).not.toHaveBeenCalled();
  });

  it("reconciles an unlocked report URL after hydration without losing the early-stage view preference", async () => {
    server.use(
      http.get("/backend/api/simulations/live-layout", () => HttpResponse.json(snapshot("report"))),
    );
    const user = userEvent.setup();

    renderWorkflow("/simulation/live-layout?step=report&mode=graph");

    expect(await screen.findByRole("heading", { name: "Susun laporan kebijakan" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Graph" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Workbench" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("region", { name: "Konsol sistem" })).not.toBeInTheDocument();

    const stepper = screen.getByRole("navigation", { name: "Tahap workflow" });
    await user.click(within(stepper).getByRole("button", { name: /Simulasi/ }));

    expect(screen.getByRole("button", { name: "Graph" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Graph" })).toBeEnabled();
  });

  it("uses normal navigation from Report to Interaction and leaves Step 05 ready", async () => {
    server.use(
      http.get("/backend/api/simulations/live-next", () => HttpResponse.json(snapshot("report"))),
    );
    const user = userEvent.setup();
    renderWorkflow("/simulation/live-next?step=report&mode=split");

    await user.click(await screen.findByRole("button", { name: "Buka interaksi →" }));

    expect(await screen.findByRole("heading", { name: "Interaksi dengan hasil" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Konsol sistem" })).not.toBeInTheDocument();
    const interactionStep = within(screen.getByRole("navigation", { name: "Tahap workflow" })).getByRole("button", { name: /Interaksi/ });
    expect(interactionStep).toHaveTextContent("Siap");
    expect(interactionStep).not.toHaveTextContent("Selesai");
  });

  it("shows a Report navigation button when the simulation is completed", async () => {
    server.use(
      http.get("/backend/api/simulations/live-completed", () => HttpResponse.json(snapshot("report"))),
    );
    const user = userEvent.setup();
    renderWorkflow("/simulation/live-completed?step=simulation&mode=split");

    const reportButton = await screen.findByRole("button", { name: "Buka laporan →" });
    await user.click(reportButton);

    expect(await screen.findByRole("heading", { name: "Susun laporan kebijakan" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Workbench" })).toHaveAttribute("aria-pressed", "true");
  });

  it("requires confirmation before starting a ready simulation", async () => {
    const ready = snapshot("simulation");
    ready.stages!.simulation = { status: "ready", progress: 0 };
    ready.simulation = { status: "ready", events: [] };
    let submitted: Record<string, unknown> | undefined;
    server.use(
      http.get("/backend/api/simulations/live-ready-run", () => HttpResponse.json(ready)),
      http.get("/backend/api/simulations/live-ready-run/runtime-graph", () => HttpResponse.json({ available: false })),
      http.post("/backend/api/simulations/live-ready-run/stages/simulation/start", async ({ request }) => {
        submitted = await request.json() as Record<string, unknown>;
        return HttpResponse.json(snapshot("simulation"));
      }),
    );
    const user = userEvent.setup();
    renderWorkflow("/simulation/live-ready-run?step=simulation&mode=workbench");

    expect(await screen.findByRole("heading", { name: "Periksa konfigurasi sebelum menjalankan" })).toBeInTheDocument();
    expect(screen.getByText(/bukan prediksi opini publik/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Mulai simulasi →" }));

    await waitFor(() => expect(submitted).toMatchObject({ rounds: 5, max_rounds: 5, enable_graph_memory_update: true }));
  });

  it("renders action-specific context in the adaptive event timeline", async () => {
    const running = snapshot("simulation");
    running.simulation = {
      status: "running",
      events: [{
        id: "quote-1",
        round: 2,
        time: "00:45",
        channel: "twitter",
        persona: "Ibu Sari",
        group: "Pelaku UMKM",
        type: "QUOTE_POST",
        statement: "Kebijakan ini perlu masa transisi.",
        stance: "Khawatir",
        concerns: ["Transisi"],
        action_args: {
          quote_content: "Kebijakan ini perlu masa transisi.",
          original_author_name: "Dinas Koperasi",
          original_content: "Registrasi dimulai bulan depan.",
        },
      }],
    };
    server.use(
      http.get("/backend/api/simulations/live-actions", () => HttpResponse.json(running)),
      http.get("/backend/api/simulations/live-actions/runtime-graph", () => HttpResponse.json({ available: false })),
    );
    renderWorkflow("/simulation/live-actions?step=simulation&mode=workbench");

    expect(await screen.findByRole("heading", { name: "Linimasa aktivitas sintetis" })).toBeInTheDocument();
    expect(screen.getByText("Kutipan")).toBeInTheDocument();
    expect(screen.getByText("Dinas Koperasi")).toBeInTheDocument();
    expect(screen.getByText("Registrasi dimulai bulan depan.")).toBeInTheDocument();
    expect(screen.getByLabelText(/Ibu Sari, Kutipan, ronde 2/)).toBeInTheDocument();
  });

  it("shows failed-run guidance without unlocking the report", async () => {
    const failed = snapshot("simulation");
    failed.stages!.simulation = { status: "failed", progress: 40, error: "Runtime OASIS terputus" };
    failed.simulation = { status: "failed", events: [], error: "Runtime OASIS terputus" };
    server.use(
      http.get("/backend/api/simulations/live-failed", () => HttpResponse.json(failed)),
      http.get("/backend/api/simulations/live-failed/runtime-graph", () => HttpResponse.json({ available: false })),
    );
    renderWorkflow("/simulation/live-failed?step=simulation&mode=workbench");

    expect(await screen.findByRole("alert")).toHaveTextContent("Runtime OASIS terputus");
    expect(screen.queryByRole("button", { name: "Buka laporan →" })).not.toBeInTheDocument();
  });

  it("renders interaction send failures in the interaction panel", async () => {
    server.use(
      http.get("/backend/api/simulations/live-chat-error", () => HttpResponse.json(snapshot("interaction"))),
      http.post("/backend/api/simulations/live-chat-error/interactions", () => HttpResponse.json({ message: "Layanan interaksi tidak tersedia" }, { status: 503 })),
    );
    const user = userEvent.setup();
    renderWorkflow("/simulation/live-chat-error?step=interaction");

    const input = await screen.findByPlaceholderText("Ajukan pertanyaan berbasis laporan...");
    await user.type(input, "Apa risiko utama?");
    await user.click(screen.getByRole("button", { name: "Kirim →" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Layanan interaksi tidak tersedia");
    expect(screen.getByRole("heading", { name: "Interaksi dengan hasil" })).toBeInTheDocument();
  });

  it("refreshes the backend snapshot after a successful interaction", async () => {
    let reads = 0;
    server.use(
      http.get("/backend/api/simulations/live-chat", () => {
        reads += 1;
        return HttpResponse.json(snapshot("interaction"));
      }),
      http.post("/backend/api/simulations/live-chat/interactions", () => HttpResponse.json({ id: "answer-1", role: "agent", author: "Report Agent", tool: "report", text: "Risiko utama telah ditinjau.", tool_calls: [], sources: [] })),
    );
    const user = userEvent.setup();
    renderWorkflow("/simulation/live-chat?step=interaction");

    const input = await screen.findByPlaceholderText("Ajukan pertanyaan berbasis laporan...");
    await user.type(input, "Apa risiko utama?");
    await user.click(screen.getByRole("button", { name: "Kirim →" }));

    expect(await screen.findByText("Risiko utama telah ditinjau.")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    await waitFor(() => expect(reads).toBe(2));
  });

  it("uses backend answers for quick demo interactions", async () => {
    const quick = snapshot("interaction");
    quick.workflow_mode = "quick_demo";
    quick.workflow = { mode: "quick_demo", demo_bundle_id: "registrasi-digital-umkm-v1" };
    quick.demo_bundle_id = "registrasi-digital-umkm-v1";
    const presentation = createWorkflowSession("quick-chat", "Program Backend");
    presentation.currentStep = 5;
    presentation.viewMode = "workbench";
    presentation.steps = {
      1: { status: "completed", progress: 100, activeTask: null },
      2: { status: "completed", progress: 100, activeTask: null },
      3: { status: "completed", progress: 100, activeTask: null },
      4: { status: "completed", progress: 100, activeTask: null },
      5: { status: "ready", progress: 0, activeTask: null },
    };
    sessionStorage.setItem(quickPresentationSessionKey("quick-chat"), JSON.stringify({ version: 2, session: presentation }));
    let submitted: Record<string, unknown> | undefined;
    server.use(
      http.get("/backend/api/simulations/quick-chat", () => HttpResponse.json(quick)),
      http.get("/backend/api/simulations/quick-chat/runtime-graph", () => HttpResponse.json({ available: false })),
      http.post("/backend/api/simulations/quick-chat/interactions", async ({ request }) => {
        submitted = await request.json() as Record<string, unknown>;
        return HttpResponse.json({ id: "quick-answer-1", role: "agent", author: "Report Agent", tool: "report", text: "Jawaban real dari backend quick demo." });
      }),
    );
    const user = userEvent.setup();
    renderWorkflow("/simulation/quick-chat?step=interaction&mode=workbench");

    const input = await screen.findByPlaceholderText("Ajukan pertanyaan berbasis laporan...");
    await user.type(input, "Apa temuan quick demo?");
    await user.click(screen.getByRole("button", { name: "Kirim →" }));

    await waitFor(() => expect(submitted).toMatchObject({ question: "Apa temuan quick demo?", tool: "report" }));
    expect(await screen.findByText("Jawaban real dari backend quick demo.")).toBeInTheDocument();
    expect(screen.queryByText(/Laporan menunjukkan bahwa/i)).not.toBeInTheDocument();
  });

  it("scrolls the message log gradually after sending a chat message", async () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
    });
    let frameId = 0;
    const frames: { id: number; callback: FrameRequestCallback }[] = [];
    const cancelledFrames = new Set<number>();
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      const id = ++frameId;
      frames.push({ id, callback });
      return id;
    });
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation((id) => {
      cancelledFrames.add(id);
    });
    const runFrames = (offset: number, done: () => boolean) => {
      let count = 0;
      while (frames.length && count < 30) {
        count += 1;
        const frame = frames.shift()!;
        if (!cancelledFrames.has(frame.id)) {
          frame.callback(window.performance.now() + offset);
          if (done()) return true;
        }
      }
      return done();
    };
    server.use(
      http.get("/backend/api/simulations/live-chat-scroll", () => HttpResponse.json(snapshot("interaction"))),
      http.get("/backend/api/simulations/live-chat-scroll/runtime-graph", () => HttpResponse.json({ available: false })),
      http.post("/backend/api/simulations/live-chat-scroll/interactions", () => HttpResponse.json({ id: "answer-scroll", role: "agent", author: "Report Agent", tool: "report", text: "Jawaban scroll." })),
    );
    const user = userEvent.setup();
    renderWorkflow("/simulation/live-chat-scroll?step=interaction");

    const log = await screen.findByRole("log", { name: "Riwayat interaksi" });
    Object.defineProperties(log, {
      clientHeight: { configurable: true, value: 120 },
      scrollHeight: { configurable: true, value: 960 },
    });
    log.scrollTop = 0;

    await user.type(screen.getByLabelText("Pertanyaan"), "Apa risiko utama?");
    await user.click(screen.getByRole("button", { name: "Kirim →" }));

    expect(log.scrollTop).toBe(0);
    expect(runFrames(340, () => log.scrollTop > 0)).toBe(true);
    expect(log.scrollTop).toBeGreaterThan(0);
    expect(log.scrollTop).toBeLessThan(840);
    expect(await screen.findByText("Jawaban scroll.")).toBeInTheDocument();
    runFrames(1200, () => log.scrollTop === 840);
    await waitFor(() => expect(log.scrollTop).toBe(840));
  });

  it("sends with Enter and keeps Shift+Enter available for multiline input", async () => {
    let submitted: Record<string, unknown> | undefined;
    server.use(
      http.get("/backend/api/simulations/live-keyboard", () => HttpResponse.json(snapshot("interaction"))),
      http.post("/backend/api/simulations/live-keyboard/interactions", async ({ request }) => {
        submitted = await request.json() as Record<string, unknown>;
        return HttpResponse.json({ id: "answer-keyboard", role: "agent", author: "Report Agent", tool: "report", text: "Jawaban keyboard." });
      }),
    );
    const user = userEvent.setup();
    renderWorkflow("/simulation/live-keyboard?step=interaction");

    const input = await screen.findByLabelText("Pertanyaan");
    await user.type(input, "Baris pertama{shift>}{enter}{/shift}baris kedua");
    expect(input).toHaveValue("Baris pertama\nbaris kedua");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(submitted).toMatchObject({ question: "Baris pertama\nbaris kedua", tool: "report" }));
    expect(await screen.findByText("Jawaban keyboard.")).toBeInTheDocument();
  });

  it("shows policy-oriented interaction modes including risk analysis", async () => {
    server.use(
      http.get("/backend/api/simulations/live-tools", () => HttpResponse.json(snapshot("interaction"))),
      http.get("/backend/api/simulations/live-tools/interviews", () => HttpResponse.json({ items: [] })),
    );
    renderWorkflow("/simulation/live-tools?step=interaction");

    const modes = await screen.findByRole("navigation", { name: "Mode interaksi" });
    expect(within(modes).getByRole("button", { name: "Tanya laporan" })).toBeInTheDocument();
    expect(within(modes).queryByRole("button", { name: "Wawancara persona" })).not.toBeInTheDocument();
    expect(within(modes).queryByRole("button", { name: "Beberapa persona" })).not.toBeInTheDocument();
    expect(within(modes).getByRole("button", { name: "Analisis risiko" })).toBeInTheDocument();
  });

  it("serializes polling and keeps a hydrated workspace visible when polling fails", async () => {
    let reads = 0;
    let activePolls = 0;
    let maxActivePolls = 0;
    server.use(
      http.get("/backend/api/simulations/live-poll", async () => {
        reads += 1;
        if (reads === 1) return HttpResponse.json(snapshot("simulation"));
        activePolls += 1;
        maxActivePolls = Math.max(maxActivePolls, activePolls);
        await delay(1700);
        activePolls -= 1;
        return HttpResponse.json({ message: "Polling sementara gagal" }, { status: 503 });
      }),
    );
    renderWorkflow("/simulation/live-poll?step=simulation&mode=workbench");

    expect(await screen.findByRole("heading", { name: "Pantau dinamika skenario" })).toBeInTheDocument();
    expect(await screen.findByRole("alert", {}, { timeout: 4000 })).toHaveTextContent("Polling sementara gagal");
    expect(screen.getByRole("heading", { name: "Pantau dinamika skenario" })).toBeInTheDocument();
    expect(maxActivePolls).toBe(1);
  });

  it("keeps full simulation event timeline pinned to the bottom while events stream in", async () => {
    const makeEvent = (index: number) => ({
      id: `event-${index}`,
      round: Math.ceil(index / 3),
      channel: index % 2 === 0 ? "reddit" : "twitter",
      persona: `Persona ${index}`,
      group: "Warga terdampak",
      type: "CREATE_POST",
      statement: `Aktivitas simulasi ${index}`,
      stance: "Netral",
      concerns: ["Akses"],
      risk_narrative: "Risiko akses layanan",
      influence_source: "Simulasi OASIS",
    });
    let reads = 0;
    server.use(
      http.get("/backend/api/simulations/live-simulation-scroll", () => {
        reads += 1;
        const state = snapshot("simulation");
        state.environment = { personas: [], persona_count: 30, config: { rounds: 12, platforms: ["twitter", "reddit"] } };
        state.simulation = {
          status: "running",
          event_count: reads > 1 ? 24 : 2,
          events: Array.from({ length: reads > 1 ? 24 : 2 }, (_, index) => makeEvent(index + 1)),
        };
        return HttpResponse.json(state);
      }),
      http.get("/backend/api/simulations/live-simulation-scroll/runtime-graph", () => HttpResponse.json({ available: false })),
    );
    renderWorkflow("/simulation/live-simulation-scroll?step=simulation&mode=workbench");

    const simulationHeading = await screen.findByRole("heading", { name: "Pantau dinamika skenario" });
    const simulationPane = simulationHeading.closest<HTMLElement>(".simulation-step")!;
    Object.defineProperties(simulationPane, {
      scrollHeight: { configurable: true, value: 2400 },
      clientHeight: { configurable: true, value: 600 },
    });
    simulationPane.scrollTop = 0;

    expect(await screen.findByText("Aktivitas simulasi 24", {}, { timeout: 4000 })).toBeInTheDocument();
    await waitFor(() => expect(simulationPane.scrollTop).toBe(2400));
  });

  it("keeps the runtime graph separate and connects Zep-shaped edges", async () => {
    server.use(
      http.get("/backend/api/simulations/live-runtime-graph", () => HttpResponse.json(snapshot("simulation"))),
      http.get("/backend/api/simulations/live-runtime-graph/runtime-graph", () => HttpResponse.json({
        available: true,
        graph_id: "zep-1",
        source_revision: 2,
        mapping_status: "running",
        node_count: 2,
        edge_count: 1,
        nodes: [
          { uuid: "runtime-a", name: "Memori A", labels: ["Entity"] },
          { uuid: "runtime-b", name: "Memori B", labels: ["Entity"] },
        ],
        edges: [{ uuid: "runtime-edge", source_node_uuid: "runtime-a", target_node_uuid: "runtime-b", fact_type: "AFFECTS" }],
      })),
    );
    const user = userEvent.setup();

    renderWorkflow("/simulation/live-runtime-graph?step=simulation&mode=graph");

    const runtimeButton = await screen.findByRole("button", { name: "Graf runtime 2/1" });
    const policyButton = screen.getByRole("button", { name: "Graf kebijakan" });
    expect(runtimeButton).toHaveClass("active");
    await user.click(policyButton);

    expect(policyButton).toHaveClass("active");
    expect(screen.getByText("GRAF PENGETAHUAN KEBIJAKAN")).toBeInTheDocument();
    await user.click(runtimeButton);

    expect(runtimeButton).toHaveClass("active");
    expect(screen.getByText("GRAF RUNTIME OASIS / ZEP")).toBeInTheDocument();
    const graph = screen.getByRole("group", { name: /Graf pemangku kepentingan dan kebijakan/ });
    await waitFor(() => expect(graph.querySelectorAll(".graph-edges line")).toHaveLength(1));
  });

  it("hydrates the public quick-demo runtime graph from its bundled snapshot", async () => {
    const quick = snapshot("report");
    quick.workflow_mode = "quick_demo";
    quick.workflow = { mode: "quick_demo", demo_bundle_id: "registrasi-digital-umkm-v1" };
    quick.runtime_graph = embeddedRuntimeGraph();
    saveQuickGraphPresentation("demo-registrasi-umkm");
    server.use(
      http.get("/backend/api/public/quick-demo", () => HttpResponse.json(quick)),
    );
    const user = userEvent.setup();

    renderWorkflow("/simulation/demo-registrasi-umkm?step=environment&mode=graph");

    const runtimeButton = await screen.findByRole("button", { name: "Graf runtime 2/1" });
    expect(runtimeButton).toBeEnabled();
    await user.click(runtimeButton);
    expect(runtimeButton).toHaveClass("active");
    expect(screen.getByText("GRAF RUNTIME OASIS / ZEP")).toBeInTheDocument();
  });

  it("prefers the authenticated quick-demo runtime graph bundled in the snapshot", async () => {
    const quick = snapshot("report");
    quick.workflow_mode = "quick_demo";
    quick.workflow = { mode: "quick_demo", demo_bundle_id: "registrasi-digital-umkm-v1" };
    quick.runtime_graph = embeddedRuntimeGraph();
    saveQuickGraphPresentation("quick-runtime");
    server.use(
      http.get("/backend/api/simulations/quick-runtime", () => HttpResponse.json(quick)),
      http.get("/backend/api/simulations/quick-runtime/runtime-graph", () =>
        HttpResponse.json({ available: false }),
      ),
    );
    const user = userEvent.setup();

    renderWorkflow("/simulation/quick-runtime?step=environment&mode=graph");

    const runtimeButton = await screen.findByRole("button", { name: "Graf runtime 2/1" });
    expect(runtimeButton).toBeEnabled();
    await user.click(runtimeButton);
    expect(runtimeButton).toHaveClass("active");
  });

  it("keeps the policy graph visible while the runtime graph is pending", async () => {
    server.use(
      http.get("/backend/api/simulations/live-pending-graph", () => HttpResponse.json(snapshot("simulation"))),
      http.get("/backend/api/simulations/live-pending-graph/runtime-graph", () => HttpResponse.json({ available: false })),
    );

    renderWorkflow("/simulation/live-pending-graph?step=simulation&mode=graph");

    expect(await screen.findByRole("button", { name: "Graf kebijakan" })).toHaveClass("active");
    expect(screen.getByRole("button", { name: "Graf runtime memuat" })).toBeDisabled();
    expect(screen.getByText("GRAF PENGETAHUAN KEBIJAKAN")).toBeInTheDocument();
  });

  it("marks a missing runtime graph unavailable after the workflow is terminal", async () => {
    server.use(
      http.get("/backend/api/simulations/live-without-runtime", () => HttpResponse.json(snapshot("report"))),
      http.get("/backend/api/simulations/live-without-runtime/runtime-graph", () =>
        HttpResponse.json({ available: false }),
      ),
    );

    renderWorkflow("/simulation/live-without-runtime?step=environment&mode=graph");

    expect(await screen.findByRole("button", { name: "Graf runtime tidak tersedia" })).toBeDisabled();
    expect(screen.getByText("GRAF PENGETAHUAN KEBIJAKAN")).toBeInTheDocument();
  });

  it("starts environment preparation with fast deterministic defaults", async () => {
    const environmentReady = snapshot("simulation");
    environmentReady.current_stage = "environment";
    environmentReady.stages!.environment = { status: "ready", progress: 0 };
    environmentReady.stages!.simulation = { status: "locked", progress: 0 };
    environmentReady.simulation = { status: "ready", events: [] };
    let submitted: Record<string, unknown> | undefined;
    server.use(
      http.get("/backend/api/simulations/live-environment", () => HttpResponse.json(environmentReady)),
      http.get("/backend/api/simulations/live-environment/runtime-graph", () => HttpResponse.json({ available: false })),
      http.post("/backend/api/simulations/live-environment/stages/environment/start", async ({ request }) => {
        submitted = await request.json() as Record<string, unknown>;
        return HttpResponse.json(environmentReady);
      }),
    );
    const user = userEvent.setup();

    renderWorkflow("/simulation/live-environment?step=environment&mode=workbench");

    const profileCount = await screen.findByRole("spinbutton", { name: "Jumlah maksimum profil" });
    const rounds = screen.getByRole("spinbutton", { name: "Jumlah ronde simulasi" });
    expect(profileCount).toHaveValue(10);
    expect(screen.queryByRole("checkbox", { name: "Perkaya setiap profil dengan LLM (lebih lambat)" })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "Perkaya konfigurasi simulasi dengan LLM (lebih lambat)" })).not.toBeInTheDocument();
    fireEvent.change(rounds, { target: { value: "10" } });
    await user.click(screen.getByRole("button", { name: "Siapkan lingkungan OASIS →" }));

    await waitFor(() => expect(submitted).toEqual({
      rounds: 10,
      max_rounds: 10,
      max_profile_count: 10,
      use_llm_for_profiles: false,
      use_llm_for_config: false,
      parallel_profile_count: 5,
    }));
  });

  it("renders Simulasi Cepat through the standard five-step workflow", async () => {
    const quick = snapshot("report");
    quick.current_stage = "graph";
    quick.workflow_mode = "quick_demo";
    quick.demo_bundle_id = "registrasi-digital-umkm-v1";
    quick.stages!.graph = { status: "completed", progress: 100, execution_kind: "accelerated_fixture" };
    quick.stages!.environment = { status: "completed", progress: 100, execution_kind: "accelerated_fixture" };
    quick.stages!.simulation = { status: "completed", progress: 100, execution_kind: "accelerated_fixture" };
    quick.stages!.report = { status: "completed", progress: 100, execution_kind: "accelerated_fixture" };
    quick.stages!.interaction = { status: "ready", progress: 0 };
    quick.simulation = {
      status: "completed",
      event_count: 1,
      events: [{
        id: "quick-event-1",
        round: 1,
        time: "2026-08-06T09:00:00+07:00",
        channel: "twitter",
        persona: "Sari Wulandari",
        group: "Pelaku usaha",
        type: "CREATE_POST",
        statement: "Pelaku usaha membutuhkan kepastian masa transisi.",
        stance: "Netral",
        concerns: ["Masa transisi"],
        risk_narrative: "Ketidakpastian dapat menunda partisipasi.",
        influence_source: "Pengumuman kebijakan",
      }, {
        id: "quick-event-2",
        round: 1,
        time: "2026-08-06T09:00:01+07:00",
        channel: "reddit",
        persona: "Ratna Prameswari",
        group: "Pemerintah daerah",
        type: "CREATE_POST",
        statement: "Registrasi dibuka bertahap melalui meja bantuan kecamatan.",
        stance: "Positif",
        concerns: ["Akses layanan"],
        risk_narrative: "Pelaku usaha membutuhkan pendampingan lokal.",
        influence_source: "Publikasi pemerintah daerah",
      }],
    };
    quick.report = {
      status: "completed",
      progress: 100,
      title: "Laporan Simulasi Registrasi Digital UMKM",
      sections: [{
        id: "summary",
        title: "Ringkasan Eksekutif",
        paragraphs: ["Respons membaik setelah kepastian masa transisi dan layanan bergerak diumumkan."],
        citations: [{ source_type: "event", source_id: "quick-event-1" }],
      }],
      risks: [],
    };
    let stageCalls = 0;
    server.use(
      http.get("/backend/api/simulations/quick-live", () => HttpResponse.json(quick)),
      http.get("/backend/api/simulations/quick-live/runtime-graph", () => HttpResponse.json({ available: false })),
      http.post("/backend/api/simulations/quick-live/stages/report/start", () => {
        stageCalls += 1;
        return HttpResponse.json({ ...quick, current_stage: "report", stages: { ...quick.stages, report: { status: "processing", progress: 0 } } });
      }),
    );
    const user = userEvent.setup();
    renderWorkflow("/simulation/quick-live?step=graph&mode=workbench");

    expect(await screen.findByRole("heading", { name: "Bangun graf kebijakan" })).toBeInTheDocument();
    const stepper = screen.getByRole("navigation", { name: "Tahap workflow" });
    expect(within(stepper).getByRole("button", { name: /Bangun Graf/ })).toHaveTextContent("0%");
    expect(within(stepper).getByRole("button", { name: /Siapkan Lingkungan/ })).toHaveTextContent("Terkunci");
    expect(within(stepper).getByRole("button", { name: /^03Simulasi/ })).toHaveTextContent("Terkunci");
    expect(screen.queryByRole("button", { name: "Mulai membangun graf →" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Simulasi Cepat|dipercepat|dikonfigurasi|tur berpindah|presentasi terpandu|lewati animasi/i)).not.toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Lanjut ke penyiapan lingkungan →" }));
    expect(await screen.findByRole("heading", { name: "Siapkan lingkungan simulasi" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Siapkan lingkungan OASIS →" }));
    await user.click(await screen.findByRole("button", { name: "Mulai simulasi →" }));
    const simulationHeading = await screen.findByRole("heading", { name: "Pantau dinamika skenario" });
    const simulationPane = simulationHeading.closest<HTMLElement>(".simulation-step")!;
    simulationPane.style.overflowY = "auto";
    const scrollTo = vi.fn();
    simulationPane.scrollTo = scrollTo;
    Object.defineProperties(simulationPane, {
      scrollHeight: { configurable: true, value: 1800 },
      clientHeight: { configurable: true, value: 600 },
    });
    await user.click(screen.getByRole("button", { name: "Mulai simulasi →" }));
    const reportButton = await screen.findByRole("button", { name: "Buka laporan →" });
    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 1800 })));
    const reportStep = within(stepper).getByRole("button", { name: /Laporan/ });
    expect(reportStep).toHaveTextContent("Terkunci");
    expect(reportStep).toBeDisabled();
    await user.click(reportButton);
    expect(await screen.findByRole("heading", { name: "Susun laporan kebijakan" })).toBeInTheDocument();
    expect(reportStep).toHaveTextContent("Siap");
    expect(reportStep).toBeEnabled();
    expect(stageCalls).toBe(0);
    await user.click(screen.getByRole("button", { name: "Susun laporan →" }));
    expect(await screen.findByText("Respons membaik setelah kepastian masa transisi dan layanan bergerak diumumkan.")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Buka interaksi →" })).toBeInTheDocument();
    expect(stageCalls).toBe(0);
  });
});
