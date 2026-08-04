import { useEffect, useEffectEvent, useRef, useState } from "react";
import { ApiError, connectSimulationStream } from "../../api/client";
import type { SimulationStreamEvent } from "../../api/client";

export type SimulationStreamStatus = "connecting" | "connected" | "reconnecting" | "error" | "closed";

export function useSimulationStream({
  simulationId,
  enabled,
  onEvent,
}: {
  simulationId: string;
  enabled: boolean;
  onEvent: (event: SimulationStreamEvent) => void;
}) {
  const [status, setStatus] = useState<SimulationStreamStatus>(enabled ? "connecting" : "closed");
  const [error, setError] = useState("");
  const lastEventId = useRef<string | undefined>(undefined);
  const cursorSimulationId = useRef(simulationId);
  const receive = useEffectEvent((message: SimulationStreamEvent) => {
    if (message.id) lastEventId.current = message.id;
    onEvent(message);
  });

  useEffect(() => {
    if (cursorSimulationId.current !== simulationId) {
      cursorSimulationId.current = simulationId;
      lastEventId.current = undefined;
    }
    if (!enabled || !simulationId) {
      return;
    }
    const controller = new AbortController();
    let retryTimer: number | undefined;
    let retries = 0;
    let opened = false;

    const connect = async () => {
      setStatus(opened ? "reconnecting" : "connecting");
      try {
        await connectSimulationStream(simulationId, {
          signal: controller.signal,
          lastEventId: lastEventId.current,
          onOpen: () => {
            opened = true;
            retries = 0;
            setError("");
            setStatus("connected");
          },
          onEvent: receive,
        });
        if (controller.signal.aborted) return;
        setError("Aliran pembaruan terputus.");
      } catch (cause) {
        if (controller.signal.aborted) return;
        const message = cause instanceof Error ? cause.message : "Koneksi pembaruan gagal.";
        setError(message);
        if (cause instanceof ApiError && (cause.status === 401 || cause.status === 403)) {
          setStatus("error");
          return;
        }
      }
      retries += 1;
      setStatus("reconnecting");
      retryTimer = window.setTimeout(connect, Math.min(15_000, 1000 * 2 ** Math.min(retries - 1, 4)));
    };

    connect();
    return () => {
      controller.abort();
      if (retryTimer) window.clearTimeout(retryTimer);
    };
  }, [enabled, simulationId]);

  const effectiveStatus: SimulationStreamStatus = enabled ? status : "closed";
  return { status: effectiveStatus, error, healthy: effectiveStatus === "connected" };
}
