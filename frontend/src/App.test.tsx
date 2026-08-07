import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { server } from "./test/server";

function LocationProbe() {
  const location = useLocation();
  return (
    <output data-testid="location">
      {location.pathname}
      {location.search}
    </output>
  );
}

function renderApp(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <App />
          <LocationProbe />
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("application routing", () => {
  it("redirects an unauthenticated protected route and preserves the destination", async () => {
    renderApp("/reports?risk=high#summary");

    expect(
      await screen.findByRole("heading", { name: "Masuk ke RekaKebijakan" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent(
      "/login?next=%2Freports%3Frisk%3Dhigh%23summary",
    );
  });

  it("navigates between public auth routes without reloading", async () => {
    const user = userEvent.setup();
    renderApp("/login");

    await user.click(await screen.findByRole("link", { name: "Daftar" }));

    expect(
      screen.getByRole("heading", { name: "Daftar ke RekaKebijakan" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/register");
  });

  it("lets guests open the quick simulation from the header", async () => {
    const user = userEvent.setup();
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        observe() {}
        disconnect() {}
      },
    );
    Object.defineProperties(SVGSVGElement.prototype, {
      width: { configurable: true, value: { baseVal: { value: 820 } } },
      height: { configurable: true, value: { baseVal: { value: 440 } } },
    });
    server.use(
      http.get("/backend/api/auth/me", () =>
        HttpResponse.json({}, { status: 401 }),
      ),
      http.get("/backend/api/public/quick-demo", () =>
        HttpResponse.json({
          project: {
            name: "Registrasi Digital UMKM",
            question: "Tinjau respons UMKM",
          },
          current_stage: "report",
          workflow_mode: "quick_demo",
          demo_bundle_id: "registrasi-digital-umkm-v1",
          workflow: {
            mode: "quick_demo",
            bundle: {
              id: "registrasi-digital-umkm-v1",
              title: "Registrasi Digital UMKM",
            },
          },
          stages: {
            graph: { status: "completed", progress: 100 },
            environment: { status: "completed", progress: 100 },
            simulation: { status: "completed", progress: 100 },
            report: { status: "completed", progress: 100 },
            interaction: { status: "ready", progress: 0 },
          },
          graph: { nodes: [], edges: [] },
          environment: {
            personas: [],
            persona_count: 0,
            config: { rounds: 5 },
          },
          simulation: { status: "completed", events: [], event_count: 0 },
          report: { status: "completed", sections: [], risks: [] },
          logs: [],
        }),
      ),
    );
    renderApp("/");

    expect(
      (await screen.findAllByText("Coba tanpa masuk")).length,
    ).toBeGreaterThan(0);
    await user.click(
      await screen.findByRole("link", { name: /Simulasi Cepat/ }),
    );

    expect(
      await screen.findByRole("heading", { name: "Registrasi Digital UMKM" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent(
      "/simulation/demo-registrasi-umkm?step=graph&mode=split",
    );
    expect(
      screen.queryByRole("heading", { name: "Masuk ke RekaKebijakan" }),
    ).not.toBeInTheDocument();
  });

  it("toggles password visibility from icon buttons without coupling register fields", async () => {
    const user = userEvent.setup();
    renderApp("/register");

    const password = (await screen.findByLabelText(
      "Kata sandi",
    )) as HTMLInputElement;
    const confirmation = screen.getByLabelText(
      "Konfirmasi kata sandi",
    ) as HTMLInputElement;
    const passwordToggle = screen.getByRole("button", {
      name: "Tampilkan kata sandi",
    });
    const confirmationToggle = screen.getByRole("button", {
      name: "Tampilkan konfirmasi kata sandi",
    });

    expect(password.type).toBe("password");
    expect(confirmation.type).toBe("password");

    await user.click(passwordToggle);

    expect(password.type).toBe("text");
    expect(confirmation.type).toBe("password");
    expect(
      screen.getByRole("button", { name: "Sembunyikan kata sandi" }),
    ).toBeInTheDocument();

    await user.click(confirmationToggle);

    expect(confirmation.type).toBe("text");
    expect(
      screen.getByRole("button", { name: "Sembunyikan konfirmasi kata sandi" }),
    ).toBeInTheDocument();
  });
});

function QuerySmoke({ queryFn }: { queryFn: () => Promise<string> }) {
  const result = useQuery({
    queryKey: ["smoke"],
    queryFn,
  });
  return <p>{result.data ?? "loading"}</p>;
}

describe("query provider", () => {
  it("executes a query through QueryClientProvider", async () => {
    const queryFn = vi.fn(async () => "query-ready");
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <QuerySmoke queryFn={queryFn} />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("query-ready")).toBeInTheDocument();
    expect(queryFn).toHaveBeenCalledOnce();
  });
});

describe("project detail resources", () => {
  it("loads the route project and creates a server-backed scenario", async () => {
    const scenarios: Array<Record<string, unknown>> = [];
    server.use(
      http.get("/backend/api/auth/me", () =>
        HttpResponse.json({
          user: { id: "user-1", name: "Analis", email: "analis@example.com" },
        }),
      ),
      http.get("/backend/api/v1/projects/project-1", () =>
        HttpResponse.json({
          id: "project-1",
          name: "Program Nyata",
          project_name: "Program Nyata",
          institution: "Instansi Uji",
          objective: "Menguji dampak kebijakan",
          status: "active",
          version: 1,
          simulation_id: "simulation-1",
          current_stage: "graph",
          workflow_status: "ready",
          highest_risk: "Rendah",
          report_available: false,
          updated_at: "2026-07-25T00:00:00Z",
          created_at: "2026-07-25T00:00:00Z",
          archived_at: null,
          documents: [
            { id: "doc-1", name: "policy.pdf", media_type: "application/pdf" },
          ],
          snapshot: {
            project: { question: "Bagaimana dampaknya?" },
            graph: { nodes: [], edges: [] },
            environment: { persona_count: 0, config: { rounds: 5 } },
          },
        }),
      ),
      http.get("/backend/api/v1/projects/project-1/scenarios", () =>
        HttpResponse.json({ items: scenarios }),
      ),
      http.post(
        "/backend/api/v1/projects/project-1/scenarios",
        async ({ request }) => {
          const input = (await request.json()) as {
            name: string;
            description: string;
          };
          const scenario = {
            id: "scenario-1",
            project_id: "project-1",
            name: input.name,
            description: input.description,
            kind: "custom",
            config: {},
            version: 1,
            created_at: "2026-07-25T00:00:00Z",
            updated_at: "2026-07-25T00:00:00Z",
            archived_at: null,
          };
          scenarios.push(scenario);
          return HttpResponse.json(scenario, { status: 201 });
        },
      ),
    );
    const user = userEvent.setup();
    renderApp("/projects/project-1");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Program Nyata" }),
    ).toBeInTheDocument();
    expect(screen.getByText("policy.pdf")).toBeInTheDocument();
    expect(screen.getAllByText("Bagaimana dampaknya?")).toHaveLength(2);

    await user.type(
      screen.getByLabelText("Nama skenario"),
      "Sosialisasi intensif",
    );
    await user.type(
      screen.getByLabelText("Deskripsi"),
      "Bandingkan kanal pendampingan",
    );
    await user.click(screen.getByRole("button", { name: "Tambah skenario" }));

    expect(
      await screen.findByText("Sosialisasi intensif", { selector: "b" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Skenario Sosialisasi intensif tersimpan."),
    ).toBeInTheDocument();
  });
});
