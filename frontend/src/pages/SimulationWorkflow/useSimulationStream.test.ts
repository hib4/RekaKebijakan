import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SimulationStreamOptions } from "../../api/client";
import { useSimulationStream } from "./useSimulationStream";

const stream = vi.hoisted(() => ({
  calls: [] as SimulationStreamOptions[],
  connect: vi.fn((_simulationId: string, options: SimulationStreamOptions) => {
    stream.calls.push(options);
    options.onOpen?.();
    return new Promise<void>((resolve) => options.signal?.addEventListener("abort", () => resolve(), { once: true }));
  }),
}));

vi.mock("../../api/client", () => ({
  ApiError: class ApiError extends Error {
    status = 500;
  },
  connectSimulationStream: stream.connect,
}));

describe("useSimulationStream", () => {
  afterEach(() => {
    stream.calls.length = 0;
    stream.connect.mockClear();
  });

  it("resets the Last-Event-ID cursor when the simulation changes", async () => {
    const onEvent = vi.fn();
    const { rerender, unmount } = renderHook(
      ({ simulationId }) => useSimulationStream({ simulationId, enabled: true, onEvent }),
      { initialProps: { simulationId: "simulation-a" } },
    );
    await waitFor(() => expect(stream.calls).toHaveLength(1));
    act(() => stream.calls[0].onEvent({ id: "event-a-9", type: "stage.updated", data: { stage: "graph" } }));

    rerender({ simulationId: "simulation-b" });

    await waitFor(() => expect(stream.calls).toHaveLength(2));
    expect(stream.calls[1].lastEventId).toBeUndefined();
    unmount();
  });
});
