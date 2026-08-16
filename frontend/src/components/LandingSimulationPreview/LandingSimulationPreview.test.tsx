import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getPublicQuickDemo } from "../../api/client";
import { LandingSimulationPreview } from "./LandingSimulationPreview";

vi.mock("../../api/client", () => ({
  getPublicQuickDemo: vi.fn(),
}));

const getPublicQuickDemoMock = vi.mocked(getPublicQuickDemo);

describe("LandingSimulationPreview", () => {
  beforeEach(() => {
    getPublicQuickDemoMock.mockRejectedValue(new Error("offline"));
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({ matches: false })),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("shows the local MBG bundle immediately when the API is unavailable", async () => {
    render(<LandingSimulationPreview onOpenWorkflow={vi.fn()} />);

    expect(screen.getByText("Bundle demo lokal")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Makan Bergizi Gratis (MBG)" })).toBeInTheDocument();
    expect(screen.getByText("30", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText("Siap menjalankan skenario")).toBeInTheDocument();
    await waitFor(() => expect(getPublicQuickDemoMock).toHaveBeenCalledOnce());
  });

  it("hydrates the idle demo from the public snapshot", async () => {
    getPublicQuickDemoMock.mockResolvedValue({
      project: {
        name: "MBG Snapshot Publik",
        question: "Apa risiko ekspansi terbaru?",
      },
      environment: {
        persona_count: 24,
        personas: Array.from({ length: 4 }, (_, index) => ({ id: `p-${index}` })),
        config: { rounds: 5, platforms: ["twitter", "reddit"] },
      },
      simulation: {
        events: [
          {
            id: "event-api",
            round: 1,
            channel: "twitter",
            persona: "Analis daerah",
            group: "Pemerintah daerah",
            type: "Tanggapan",
            statement: "Kapasitas wilayah perlu ditinjau.",
          },
        ],
      },
      report: {
        sections: [{ title: "Ringkasan", paragraphs: ["Temuan snapshot publik."] }],
        risks: [{ title: "Kesiapan wilayah", level: "high", trend: "stable", evidence: "Jejak API." }],
      },
    });

    render(<LandingSimulationPreview onOpenWorkflow={vi.fn()} />);

    expect(await screen.findByText("Snapshot demo publik")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "MBG Snapshot Publik" })).toBeInTheDocument();
    expect(screen.getByText("24", { selector: "dd" })).toBeInTheDocument();
  });

  it("runs five representative rounds, reveals findings, and can run again", async () => {
    vi.useFakeTimers();
    render(<LandingSimulationPreview onOpenWorkflow={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /Jalankan demo singkat/ }));
    expect(screen.getByRole("button", { name: /Demo sedang berjalan/ })).toBeDisabled();

    await act(async () => {
      vi.advanceTimersByTime(850);
    });
    expect(screen.getByText("Ronde 1 dari 5")).toBeInTheDocument();
    expect(screen.getByText(/desain saat ini terlalu bergantung/)).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(3400);
    });
    expect(screen.getByText("Demo selesai ditinjau")).toBeInTheDocument();
    expect(screen.getByText(/MBG berisiko menjadi proyek logistik mahal/)).toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.textContent === "8 total event")).toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.textContent === "3 risiko utama")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Jalankan ulang/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Lihat jejak bukti/ }));
    expect(screen.getByText("Program tidak tepat sasaran")).toBeInTheDocument();
  });

  it("finishes immediately for reduced-motion users", () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({ matches: true })),
    });
    render(<LandingSimulationPreview onOpenWorkflow={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /Jalankan demo singkat/ }));

    expect(screen.getByText("Demo selesai ditinjau")).toBeInTheDocument();
    expect(
      within(screen.getByLabelText("Progres 5 dari 5 ronde")).getByText("Ronde 5"),
    ).toHaveClass("done");
  });

  it("opens the complete public workflow from the finished demo", () => {
    const onOpenWorkflow = vi.fn();
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({ matches: true })),
    });
    render(<LandingSimulationPreview onOpenWorkflow={onOpenWorkflow} />);

    fireEvent.click(screen.getByRole("button", { name: /Jalankan demo singkat/ }));
    fireEvent.click(screen.getByRole("button", { name: /Lihat workflow lengkap/ }));

    expect(onOpenWorkflow).toHaveBeenCalledOnce();
  });
});
