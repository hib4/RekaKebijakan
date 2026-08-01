import { expect, test, type APIResponse, type Page } from "@playwright/test";
import { writeFile } from "node:fs/promises";

const runOasisE2E = process.env.RUN_OASIS_E2E === "true";
const stageTimeout = Number(process.env.OASIS_STAGE_TIMEOUT_MS ?? 900_000);

type Snapshot = {
  stages: Record<string, { status: string; error?: unknown }>;
};

async function responseJson<T>(response: APIResponse): Promise<T> {
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json() as Promise<T>;
}

async function waitForStage(page: Page, simulationId: string, stage: string) {
  await expect
    .poll(
      async () => {
        const response = await page.request.get(`/backend/api/simulations/${simulationId}`);
        const snapshot = await responseJson<Snapshot>(response);
        const current = snapshot.stages[stage];
        if (current.status === "failed" || current.status === "cancelled") {
          throw new Error(`${stage} ended as ${current.status}: ${JSON.stringify(current.error)}`);
        }
        return current.status;
      },
      { message: `wait for ${stage} completion`, timeout: stageTimeout, intervals: [1_000, 2_000, 5_000] },
    )
    .toBe("completed");
}

test.describe("OASIS workflow", () => {
  test.skip(!runOasisE2E, "Set RUN_OASIS_E2E=true to run the external OASIS workflow");

  test("completes steps 1 through 5 using OASIS", async ({ page }) => {
    test.setTimeout(stageTimeout * 4);

    const nonce = `${Date.now()}-${process.pid}`;
    const email = `oasis-e2e-${nonce}@example.test`;
    let projectId = "";
    let simulationId = "";

    await page.route("**/backend/api/simulations/*/stages/environment/start", async (route) => {
      const request = route.request();
      const payload = request.postDataJSON() as Record<string, unknown>;
      await route.continue({
        postData: JSON.stringify({
          ...payload,
          engine: "oasis",
          rounds: 3,
          max_rounds: 3,
          max_profile_count: 5,
          parallel_profile_count: 3,
          use_llm_for_profiles: false,
        }),
        headers: { ...request.headers(), "content-type": "application/json" },
      });
    });
    await page.route("**/backend/api/simulations/*/stages/simulation/start", async (route) => {
      const request = route.request();
      const payload = request.postDataJSON() as Record<string, unknown>;
      await route.continue({
        postData: JSON.stringify({ ...payload, engine: "oasis", max_rounds: 3 }),
        headers: { ...request.headers(), "content-type": "application/json" },
      });
    });

    try {
      await page.goto("/register?next=%2Fprojects%2Fnew");
      await page.getByRole("textbox", { name: "Nama lengkap" }).fill("OASIS E2E");
      await page.getByRole("textbox", { name: "Email" }).fill(email);
      await page.getByLabel("Kata sandi", { exact: true }).fill("oasis-e2e-password");
      await page.getByLabel("Konfirmasi kata sandi").fill("oasis-e2e-password");
      await page.getByRole("button", { name: "Buat akun" }).click();

      await expect(page.getByRole("heading", { name: "Buat Proyek Kebijakan" })).toBeVisible();
      await page.getByRole("textbox", { name: "Nama proyek" }).fill(`OASIS E2E ${nonce}`);
      await page.getByRole("textbox", { name: "Instansi/tim" }).fill("E2E Test");
      await page
        .getByPlaceholder("Jelaskan hal yang ingin diuji melalui simulasi skenario...")
        .fill("Evaluate affordability, accessibility, operator sustainability, and public response");
      await page.locator('input[type="file"]').setInputFiles({
        name: "oasis-policy.md",
        mimeType: "text/markdown",
        buffer: Buffer.from(
          [
            "# Kebijakan Tarif Transportasi Publik",
            "Pemerintah kota akan menerapkan tarif transportasi terpadu.",
            "Tarif pelajar dan kelompok berpenghasilan rendah harus terjangkau.",
            "Operator membutuhkan kompensasi agar kualitas layanan tetap terjaga.",
            "Organisasi penyandang disabilitas meminta aksesibilitas kendaraan dan halte.",
            "Evaluasi dilakukan berdasarkan keterjangkauan, jumlah penumpang, ketepatan waktu, dan keluhan.",
          ].join("\n"),
        ),
      });

      const createdResponse = page.waitForResponse(
        (response) => response.url().endsWith("/backend/api/projects") && response.request().method() === "POST",
      );
      await page.getByRole("button", { name: /Buat Proyek & Bangun Graf/ }).click();
      const created = await responseJson<{ id: string; simulation_id: string }>(await createdResponse);
      projectId = created.id;
      simulationId = created.simulation_id;

      await expect(page.getByRole("heading", { name: "Bangun graf kebijakan" })).toBeVisible();
      await waitForStage(page, simulationId, "graph");
      await page.reload();
      await page.getByRole("button", { name: "Continue to Env Setup →" }).click();

      await expect(page.getByRole("heading", { name: "Siapkan lingkungan simulasi" })).toBeVisible();
      await page.getByRole("spinbutton", { name: "Jumlah maksimum profil" }).fill("5");
      await page.getByRole("button", { name: "Prepare OASIS Environment →" }).click();
      await waitForStage(page, simulationId, "environment");

      const environment = await responseJson<{
        persona_count: number;
        personas: Array<{ id: string }>;
        config: { engine: string; generated_by: string };
      }>(await page.request.get(`/backend/api/simulations/${simulationId}/environment`));
      expect(environment.persona_count).toBeGreaterThan(0);
      expect(environment.persona_count).toBeLessThanOrEqual(5);
      expect(environment.personas.every((persona) => persona.id.startsWith("oasis-"))).toBeTruthy();
      expect(environment.config).toMatchObject({ engine: "oasis", generated_by: "oasis-direct" });

      await page.reload();
      await page.getByRole("button", { name: "Start Simulation →" }).click();
      await expect(page.getByRole("heading", { name: "Jalankan simulasi OASIS" })).toBeVisible();
      await page.getByRole("button", { name: "Start Simulation →" }).click();
      await waitForStage(page, simulationId, "simulation");

      const oasisStatus = await responseJson<{
        enabled: boolean;
        mapping_status: string;
        zep_graph_id: string;
        external_simulation_id: string;
        total_actions: number;
        platform_counts: Record<string, number>;
        runtime: Record<string, unknown>;
      }>(await page.request.get(`/backend/api/simulations/${simulationId}/oasis/status`));
      expect(oasisStatus).toMatchObject({
        enabled: true,
        mapping_status: "completed",
        runtime: { runner_status: "completed", twitter_completed: true, reddit_completed: true },
      });
      expect(oasisStatus.zep_graph_id).toBeTruthy();
      expect(oasisStatus.external_simulation_id).toBeTruthy();
      expect(oasisStatus.total_actions).toBeGreaterThan(0);
      expect(Object.keys(oasisStatus.platform_counts)).toEqual(expect.arrayContaining(["twitter", "reddit"]));

      const events = await responseJson<{ events: Array<{ id: string; persona_id: string }>; event_count: number }>(
        await page.request.get(`/backend/api/runs/${simulationId}/events`),
      );
      expect(events.event_count).toBeGreaterThan(0);
      expect(events.events.every((event) => event.id.startsWith("oasis-event-"))).toBeTruthy();
      expect(events.events.every((event) => event.persona_id.startsWith("oasis-"))).toBeTruthy();

      await page.reload();
      await page.getByRole("button", { name: "Buka Report →" }).click();
      await expect(page.getByRole("heading", { name: "Generate policy report" })).toBeVisible();
      await page.getByRole("button", { name: "Generate Report →" }).click();
      await waitForStage(page, simulationId, "report");

      const report = await responseJson<{ generated_by: string; sections: unknown[] }>(
        await page.request.get(`/backend/api/reports/${simulationId}`),
      );
      expect(report.generated_by).toBe("rekakebijakan-oasis-report-agent");
      expect(report.sections.length).toBeGreaterThan(0);

      await page.reload();
      await page.getByRole("button", { name: "Go to Interaction →" }).click();
      await expect(page.getByRole("heading", { name: "Interaksi dengan hasil" })).toBeVisible();
      const question = "Apa risiko utama kebijakan ini dan tindakan mitigasi yang paling kuat didukung oleh bukti?";
      await page.getByPlaceholder("Ajukan pertanyaan berbasis laporan...").fill(question);
      await page.getByRole("button", { name: "Send →" }).click();
      await expect(page.getByText(question)).toBeVisible();
      await expect
        .poll(
          async () => {
            const response = await page.request.get(`/backend/api/interactions/${simulationId}/messages`);
            const body = await responseJson<{ messages: Array<{ role: string; text: string }> }>(response);
            return body.messages.filter((message) => message.role === "assistant" && message.text.trim()).length;
          },
          { timeout: stageTimeout, intervals: [1_000, 2_000, 5_000] },
        )
        .toBeGreaterThan(0);

      const finalSnapshot = await responseJson<Snapshot>(
        await page.request.get(`/backend/api/simulations/${simulationId}`),
      );
      expect(finalSnapshot.stages.interaction.status).toBe("completed");

      if (process.env.OASIS_E2E_RESULT_FILE) {
        await writeFile(
          process.env.OASIS_E2E_RESULT_FILE,
          JSON.stringify({ projectId, simulationId, email }),
          "utf8",
        );
      }
    } finally {
      if (projectId) {
        await page.request.delete(`/backend/api/v1/projects/${projectId}`).catch(() => undefined);
      }
    }
  });
});
