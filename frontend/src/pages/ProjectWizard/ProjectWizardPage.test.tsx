import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectWizardPage from "./ProjectWizardPage";

const createProjectMock = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", () => ({ createProject: createProjectMock }));
vi.mock("../../components/AppShell/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}</output>;
}

function renderWizard() {
  const view = render(<MemoryRouter initialEntries={["/projects/new"]}><ProjectWizardPage /><LocationProbe /></MemoryRouter>);
  return view;
}

function renderFullWizard() {
  const view = renderWizard();
  fireEvent.click(screen.getByRole("radio", { name: /Simulasi lengkap/ }));
  fireEvent.change(screen.getByLabelText("Nama proyek"), { target: { value: "Program Uji" } });
  fireEvent.change(screen.getByLabelText("Instansi/tim"), { target: { value: "Tim Kebijakan" } });
  fireEvent.change(screen.getByPlaceholderText("Jelaskan hal yang ingin diuji melalui simulasi skenario..."), { target: { value: "Bagaimana dampaknya?" } });
  return { input: document.querySelector<HTMLInputElement>('input[type="file"]')!, ...view };
}

describe("project creation wizard", () => {
  beforeEach(() => {
    createProjectMock.mockReset();
    sessionStorage.clear();
  });

  it("visibly rejects unsupported, oversized, and excess files", () => {
    const { input } = renderFullWizard();
    const oversized = new File(["x"], "large.pdf", { type: "application/pdf" });
    Object.defineProperty(oversized, "size", { value: 16 * 1024 * 1024 + 1 });
    fireEvent.change(input, { target: { files: [new File(["x"], "image.png"), oversized] } });

    expect(screen.getByRole("alert")).toHaveTextContent("image.png: tipe berkas tidak didukung");
    expect(screen.getByRole("alert")).toHaveTextContent("large.pdf: ukuran melebihi 16 MB");

    const files = Array.from({ length: 21 }, (_, index) => new File(["x"], `policy-${index}.txt`));
    fireEvent.change(input, { target: { files } });
    expect(screen.getByRole("alert")).toHaveTextContent("Maksimal 20 berkas per proyek");
    expect(screen.getAllByRole("button", { name: /^Hapus policy-/ })).toHaveLength(20);
  });

  it("synchronously blocks duplicate submits, shows progress, and opens the graph workflow", async () => {
    let resolveRequest: (value: { simulation_id: string }) => void = () => undefined;
    createProjectMock.mockImplementation(() => new Promise((resolve) => { resolveRequest = resolve; }));
    const { input } = renderFullWizard();
    fireEvent.change(input, { target: { files: [new File(["policy"], "policy.txt")] } });
    const submitButton = screen.getByRole("button", { name: /Buat Proyek & Bangun Graf/ });
    const form = submitButton.closest("form")!;

    fireEvent.submit(form);
    fireEvent.submit(form);

    expect(createProjectMock).toHaveBeenCalledOnce();
    expect(createProjectMock.mock.calls[0][1]).toMatchObject({ idempotencyKey: expect.any(String), signal: expect.any(AbortSignal) });
    act(() => createProjectMock.mock.calls[0][1].onUploadProgress(42));
    expect(submitButton).toHaveTextContent("Buat Proyek & Bangun Graf");
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "42");
    expect(screen.getByLabelText("Nama proyek")).toBeDisabled();
    expect(input).toBeDisabled();

    resolveRequest({ simulation_id: "simulation/1" });
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/simulation/simulation%2F1?step=graph&mode=split"));
  });

  it("aborts an active upload when unmounted", () => {
    createProjectMock.mockImplementation((_input, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
    }));
    const { input, unmount } = renderFullWizard();
    fireEvent.change(input, { target: { files: [new File(["policy"], "policy.txt")] } });
    fireEvent.click(screen.getByRole("button", { name: /Buat Proyek & Bangun Graf/ }));
    const signal = createProjectMock.mock.calls[0][1].signal as AbortSignal;

    expect(signal.aborted).toBe(false);
    unmount();
    expect(signal.aborted).toBe(true);
  });

  it("prefills and submits Simulasi Cepat without requiring files", async () => {
    createProjectMock.mockResolvedValue({ simulation_id: "quick-1" });
    sessionStorage.setItem("rekakebijakan-quick-presentation:quick-1", "stale");
    renderWizard();

    const modeOptions = screen.getAllByRole("radio");
    expect(modeOptions[0]).toHaveAccessibleName(/Simulasi Cepat/);
    expect(modeOptions[1]).toHaveAccessibleName(/Simulasi lengkap/);
    expect(modeOptions[0]).toBeChecked();
    expect(screen.getByLabelText("Nama proyek")).toHaveValue("Registrasi Digital UMKM");
    expect(screen.getByLabelText("Instansi/tim")).toHaveValue("Dinas Koperasi dan UMKM");
    expect(document.querySelector('input[type="file"]')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Mulai Simulasi Cepat →" }));

    await waitFor(() => expect(createProjectMock).toHaveBeenCalledOnce());
    await waitFor(() => expect(sessionStorage.getItem("rekakebijakan-quick-presentation:quick-1")).toBeNull());
    expect(createProjectMock.mock.calls[0][0]).toMatchObject({
      projectName: "Registrasi Digital UMKM",
      files: [],
      workflowMode: "quick_demo",
      demoBundleId: "registrasi-digital-umkm-v1",
    });
  });
});
