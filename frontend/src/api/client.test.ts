import { afterEach, describe, expect, it, vi } from "vitest";
import { connectSimulationStream, controlRun, createProject, duplicateProject, getCurrentUser, loginUser, submitContact } from "./client";

describe("authentication API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("includes credentials and unwraps the current user", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ user: { id: "user_1", name: "Hiba", email: "hiba@example.com" } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getCurrentUser()).resolves.toMatchObject({ id: "user_1", email: "hiba@example.com" });
    expect(fetchMock).toHaveBeenCalledWith("/backend/api/auth/me", expect.objectContaining({ credentials: "include" }));
  });

  it("parses the backend nested error envelope", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      message: "Email atau kata sandi salah",
      error: { code: "unauthorized", message: "Email atau kata sandi salah" },
    }), { status: 401, headers: { "Content-Type": "application/json" } })));

    await expect(loginUser({ email: "hiba@example.com", password: "wrong-password" })).rejects.toMatchObject({
      status: 401,
      code: "unauthorized",
      message: "Email atau kata sandi salah",
    });
  });
});

describe("simulation SSE client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("skips malformed JSON frames and continues parsing later events", async () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("event: graph.delta\ndata: {broken\n\nevent: graph.delta\nid: 8\ndata: {\"graph_kind\":\"policy\",\"graph\":{\"nodes\":[]}}\n\n"));
        controller.close();
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } })));
    const onEvent = vi.fn();

    await connectSimulationStream("simulation-1", { onEvent });

    expect(onEvent).toHaveBeenCalledOnce();
    expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({ id: "8", type: "graph.delta", data: expect.objectContaining({ graph_kind: "policy" }) }));
  });
});

class FakeXMLHttpRequest extends EventTarget {
  static latest: FakeXMLHttpRequest;
  upload = new EventTarget();
  status = 0;
  responseText = "";
  withCredentials = false;
  method = "";
  url = "";
  body: Document | XMLHttpRequestBodyInit | null = null;
  headers: Record<string, string> = {};

  constructor() {
    super();
    FakeXMLHttpRequest.latest = this;
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  send(body: Document | XMLHttpRequestBodyInit | null) {
    this.body = body;
  }

  abort() {
    this.dispatchEvent(new Event("abort"));
  }
}

describe("project creation API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses credentialed XHR and reports upload progress with an idempotency key", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXMLHttpRequest);
    const onUploadProgress = vi.fn();
    const onUploadComplete = vi.fn();
    const result = createProject({
      projectName: "Uji kebijakan",
      institution: "Tim Uji",
      objective: "Memahami dampak",
      files: [new File(["policy"], "policy.txt", { type: "text/plain" })],
    }, { idempotencyKey: "project-key-1", onUploadProgress, onUploadComplete });

    const xhr = FakeXMLHttpRequest.latest;
    expect(xhr.method).toBe("POST");
    expect(xhr.url).toBe("/backend/api/projects");
    expect(xhr.withCredentials).toBe(true);
    expect(xhr.headers["Idempotency-Key"]).toBe("project-key-1");
    expect(xhr.body).toBeInstanceOf(FormData);

    xhr.upload.dispatchEvent(new ProgressEvent("progress", { lengthComputable: true, loaded: 5, total: 10 }));
    xhr.upload.dispatchEvent(new Event("load"));
    xhr.status = 201;
    xhr.responseText = JSON.stringify({ simulation_id: "simulation-1" });
    xhr.dispatchEvent(new Event("load"));

    await expect(result).resolves.toEqual({ simulation_id: "simulation-1" });
    expect(onUploadProgress).toHaveBeenCalledWith(50);
    expect(onUploadComplete).toHaveBeenCalledOnce();
  });

  it("preserves backend error-envelope parsing for XHR uploads", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXMLHttpRequest);
    const result = createProject({ projectName: "P", institution: "I", objective: "O", files: [] });
    const xhr = FakeXMLHttpRequest.latest;
    xhr.status = 422;
    xhr.responseText = JSON.stringify({ error: { code: "invalid_document", message: "Dokumen tidak valid", details: { field: "files" } } });
    xhr.dispatchEvent(new Event("load"));

    await expect(result).rejects.toMatchObject({ status: 422, code: "invalid_document", message: "Dokumen tidak valid", details: { field: "files" } });
  });

  it("submits the Quick Demo mode and bundle without files", () => {
    vi.stubGlobal("XMLHttpRequest", FakeXMLHttpRequest);
    createProject({
      projectName: "Registrasi Digital UMKM",
      institution: "Dinas Koperasi dan UMKM",
      objective: "Tinjau respons UMKM",
      files: [],
      workflowMode: "quick_demo",
      demoBundleId: "registrasi-digital-umkm-v1",
    });

    const body = FakeXMLHttpRequest.latest.body as FormData;
    expect(body.get("workflow_mode")).toBe("quick_demo");
    expect(body.get("demo_bundle_id")).toBe("registrasi-digital-umkm-v1");
    expect(body.getAll("files")).toHaveLength(0);
  });
});

describe("workspace v1 API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses the explicit duplicate endpoint instead of recreating a project client-side", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "copy-1" }), { status: 201, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await duplicateProject("project/1", { name: "Salinan" });

    expect(fetchMock).toHaveBeenCalledWith("/backend/api/v1/projects/project%2F1/duplicate", expect.objectContaining({
      method: "POST",
      credentials: "include",
      body: JSON.stringify({ name: "Salinan" }),
    }));
  });

  it("sends optimistic version data when controlling a run", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "run-1", status: "paused" }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await controlRun("run-1", "pause", 7);

    expect(fetchMock).toHaveBeenCalledWith("/backend/api/v1/runs/run-1/pause", expect.objectContaining({ body: JSON.stringify({ expected_version: 7 }) }));
  });

  it("submits the public contact form to the versioned contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "contact-1" }), { status: 201, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await submitContact({ name: "Hiba", organization: "Lab", email: "hiba@example.com", use_case: "Pilot" });

    expect(fetchMock).toHaveBeenCalledWith("/backend/api/v1/contact-requests", expect.objectContaining({ method: "POST", credentials: "include" }));
  });
});
