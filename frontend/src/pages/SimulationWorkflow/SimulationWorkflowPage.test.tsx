import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { delay, http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "../../test/server";
import { AuthContext } from "../../auth/auth-context";
import SimulationWorkflowPage from "./SimulationWorkflowPage";

const auth = {
  user: { id: "user-1", name: "Analis", email: "analis@example.com" },
  loading: false,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
};

function snapshot(currentStage: "graph" | "simulation" | "report" | "interaction" = "report") {
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
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
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

    expect(await screen.findByRole("heading", { name: "Generate policy report" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Graph" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Workbench" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("region", { name: "System console" })).not.toBeInTheDocument();

    const stepper = screen.getByRole("navigation", { name: "Tahap workflow" });
    await user.click(within(stepper).getByRole("button", { name: /Simulation/ }));

    expect(screen.getByRole("button", { name: "Graph" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Graph" })).toBeEnabled();
  });

  it("uses normal navigation from Report to Interaction and leaves Step 05 ready", async () => {
    server.use(
      http.get("/backend/api/simulations/live-next", () => HttpResponse.json(snapshot("report"))),
    );
    const user = userEvent.setup();
    renderWorkflow("/simulation/live-next?step=report&mode=split");

    await user.click(await screen.findByRole("button", { name: "Go to Interaction →" }));

    expect(await screen.findByRole("heading", { name: "Interaksi dengan hasil" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "System console" })).not.toBeInTheDocument();
    const interactionStep = within(screen.getByRole("navigation", { name: "Tahap workflow" })).getByRole("button", { name: /Interaction/ });
    expect(interactionStep).toHaveTextContent("ready");
    expect(interactionStep).not.toHaveTextContent("completed");
  });

  it("shows a Report navigation button when the simulation is completed", async () => {
    server.use(
      http.get("/backend/api/simulations/live-completed", () => HttpResponse.json(snapshot("report"))),
    );
    const user = userEvent.setup();
    renderWorkflow("/simulation/live-completed?step=simulation&mode=split");

    const reportButton = await screen.findByRole("button", { name: "Buka Report →" });
    await user.click(reportButton);

    expect(await screen.findByRole("heading", { name: "Generate policy report" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Workbench" })).toHaveAttribute("aria-pressed", "true");
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
    await user.click(screen.getByRole("button", { name: "Send →" }));

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
      http.post("/backend/api/simulations/live-chat/interactions", () => HttpResponse.json({ id: "answer-1", role: "agent", author: "Report Agent", tool: "report", text: "Risiko utama telah ditinjau." })),
    );
    const user = userEvent.setup();
    renderWorkflow("/simulation/live-chat?step=interaction");

    const input = await screen.findByPlaceholderText("Ajukan pertanyaan berbasis laporan...");
    await user.type(input, "Apa risiko utama?");
    await user.click(screen.getByRole("button", { name: "Send →" }));

    expect(await screen.findByText("Risiko utama telah ditinjau.")).toBeInTheDocument();
    await waitFor(() => expect(reads).toBe(2));
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

    expect(await screen.findByRole("heading", { name: "Jalankan simulasi skenario" })).toBeInTheDocument();
    expect(await screen.findByRole("alert", {}, { timeout: 4000 })).toHaveTextContent("Polling sementara gagal");
    expect(screen.getByRole("heading", { name: "Jalankan simulasi skenario" })).toBeInTheDocument();
    expect(maxActivePolls).toBe(1);
  });
});
