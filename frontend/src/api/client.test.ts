import { afterEach, describe, expect, it, vi } from "vitest";
import { createProject, getCurrentUser, loginUser } from "./client";

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
});
