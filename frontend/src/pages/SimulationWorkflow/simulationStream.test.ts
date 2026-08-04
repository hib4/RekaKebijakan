import { describe, expect, it } from "vitest";
import type { ApiSimulationSnapshot, SimulationStreamEvent } from "../../api/client";
import { mergeRuntimeGraphEvent, mergeSimulationStreamEvent } from "./simulationStream";

const base: ApiSimulationSnapshot = {
  simulation: { events: [{ id: "event-1", statement: "Awal" }], event_count: 1 },
  report: { sections: [] },
};

describe("simulation stream merging", () => {
  it("upserts repeated simulation events idempotently", () => {
    const message: SimulationStreamEvent = {
      type: "simulation.event",
      data: { event: { id: "event-1", statement: "Diperbarui" }, event_count: 1 },
    };
    const once = mergeSimulationStreamEvent(base, message);
    const twice = mergeSimulationStreamEvent(once, message);

    expect(twice.simulation?.events).toHaveLength(1);
    expect(twice.simulation?.events?.[0].statement).toBe("Diperbarui");
    expect(twice.simulation?.event_count).toBe(1);
  });

  it("reveals report sections progressively without duplicating them", () => {
    const message: SimulationStreamEvent = {
      type: "report.section",
      data: { section: { id: "ringkasan", title: "Ringkasan", content: "**Temuan** baru" }, progress: 50 },
    };
    const once = mergeSimulationStreamEvent(base, message);
    const twice = mergeSimulationStreamEvent(once, message);

    expect(twice.report?.sections).toEqual([{ id: "ringkasan", title: "Ringkasan", content: "**Temuan** baru" }]);
    expect(twice.report?.progress).toBe(50);
  });

  it("routes policy and runtime graph events independently", () => {
    const policy = mergeSimulationStreamEvent(base, {
      type: "graph.snapshot",
      data: { graph: { graph_kind: "policy", graph_id: "policy-1", build_id: "build-1", revision: 1, nodes: [{ id: "policy-node", label: "Policy" }], edges: [] } },
    });
    const runtime = mergeRuntimeGraphEvent(null, {
      type: "graph.snapshot",
      data: { graph: { graph_kind: "runtime", graph_id: "runtime-1", build_id: "run-1", revision: 1, nodes: [{ id: "runtime-node", label: "Runtime" }], edges: [] } },
    });

    expect(policy.graph?.nodes?.map((node) => node.id)).toEqual(["policy-node"]);
    expect(runtime?.nodes.map((node) => node.id)).toEqual(["runtime-node"]);
    expect(mergeRuntimeGraphEvent(null, {
      type: "graph.snapshot",
      data: { graph: { graph_kind: "policy", graph_id: "policy-1", nodes: [], edges: [] } },
    })).toBeNull();
  });

  it("preserves out-of-order edges and applies node deltas idempotently", () => {
    const snapshot = mergeRuntimeGraphEvent(null, {
      type: "graph.snapshot",
      data: { graph: { graph_kind: "runtime", graph_id: "runtime-1", build_id: "run-1", revision: 1, nodes: [{ id: "node-1", label: "A" }], edges: [] } },
    });
    const withEdge = mergeRuntimeGraphEvent(snapshot, {
      type: "graph.delta",
      data: { graph: { graph_kind: "runtime", graph_id: "runtime-1", build_id: "run-1", revision: 2, nodes: [], edges: [{ id: "edge-1", source: "node-1", target: "node-2" }] } },
    });
    const nodeLater: SimulationStreamEvent = {
      type: "graph.delta",
      data: { graph: { graph_kind: "runtime", graph_id: "runtime-1", build_id: "run-1", revision: 3, nodes: [{ id: "node-2", label: "B" }], edges: [] } },
    };
    const complete = mergeRuntimeGraphEvent(withEdge, nodeLater);
    const repeated = mergeRuntimeGraphEvent(complete, nodeLater);

    expect(withEdge?.edges).toHaveLength(1);
    expect(repeated).toMatchObject({ node_count: 2, edge_count: 1 });
    expect(repeated?.nodes).toHaveLength(2);
  });

  it("cascades incident edges on removal and rejects stale or cross-build deltas", () => {
    const current = mergeRuntimeGraphEvent(null, {
      type: "graph.snapshot",
      data: { graph: { graph_kind: "runtime", graph_id: "runtime-1", build_id: "run-1", revision: 5, nodes: [{ id: "a" }, { id: "b" }], edges: [{ id: "ab", source: "a", target: "b" }] } },
    });
    const stale = mergeRuntimeGraphEvent(current, {
      type: "graph.delta",
      data: { graph: { graph_kind: "runtime", graph_id: "runtime-1", build_id: "run-1", revision: 4, nodes: [{ id: "stale" }], edges: [] } },
    });
    const wrongBuild = mergeRuntimeGraphEvent(current, {
      type: "graph.delta",
      data: { graph: { graph_kind: "runtime", graph_id: "runtime-1", build_id: "run-2", revision: 6, nodes: [{ id: "wrong" }], edges: [] } },
    });
    const removed = mergeRuntimeGraphEvent(current, {
      type: "graph.delta",
      data: { graph: { graph_kind: "runtime", graph_id: "runtime-1", build_id: "run-1", revision: 6, removed_node_ids: ["a"] } },
    });

    expect(stale).toBe(current);
    expect(wrongBuild).toBe(current);
    expect(removed).toMatchObject({ node_count: 1, edge_count: 0 });
    expect(removed?.edges).toEqual([]);
  });
});
