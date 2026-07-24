import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { server } from "../../test/server";
import { AuthContext } from "../../auth/auth-context";
import SimulationWorkflowPage from "./SimulationWorkflowPage";

describe("SimulationWorkflowPage live mode", () => {
  afterEach(() => vi.restoreAllMocks());

  it("loads a non-demo ID only from the backend without local initialization", async () => {
    const storageRead = vi.spyOn(Storage.prototype, "getItem");
    const storageWrite = vi.spyOn(Storage.prototype, "setItem");
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
    });
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

    render(
      <MemoryRouter initialEntries={["/simulation/live-123"]}>
        <AuthContext value={{ user: { id: "user-1", name: "Analis", email: "analis@example.com" }, loading: false, login: vi.fn(), register: vi.fn(), logout: vi.fn() }}>
          <Routes>
            <Route path="/simulation/:simulationId" element={<SimulationWorkflowPage />} />
          </Routes>
        </AuthContext>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Program Backend" })).toBeInTheDocument();
    expect(screen.queryByText("Registrasi Digital UMKM")).not.toBeInTheDocument();
    expect(storageRead).not.toHaveBeenCalled();
    expect(storageWrite).not.toHaveBeenCalled();
  });
});
