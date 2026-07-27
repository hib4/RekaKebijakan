import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Citation } from "../../pages/SimulationWorkflow/workflowTypes";
import "./CitationDrawer.css";

function locatorText(locator?: Record<string, unknown>) {
  if (!locator) return "Locator tidak tersedia";
  const entries = Object.entries(locator).filter(([, value]) => value !== null && value !== undefined && value !== "");
  return entries.length ? entries.map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`).join(" · ") : "Locator tidak tersedia";
}

export function CitationDrawer({ citations, label = "Lihat sumber" }: { citations?: Citation[]; label?: string }) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const trigger = triggerRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
      trigger?.focus();
    };
  }, [open]);

  if (!citations?.length) return null;
  return (
    <>
      <button ref={triggerRef} type="button" className="citation-trigger" onClick={() => setOpen(true)}>
        {label} ({citations.length})
      </button>
      {open &&
        createPortal(
          <div
            className="citation-backdrop"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) setOpen(false);
            }}
          >
            <aside className="citation-drawer" role="dialog" aria-modal="true" aria-labelledby={titleId}>
              <header className="citation-drawer-header">
                <div>
                  <span className="citation-drawer-eyebrow">EVIDENCE TRACE</span>
                  <h2 id={titleId}>Sumber kutipan</h2>
                </div>
                <button ref={closeRef} type="button" onClick={() => setOpen(false)} aria-label="Tutup sumber kutipan">
                  Tutup
                </button>
              </header>
              <div className="citation-list">
                {citations.map((citation, index) => (
                  <article className="citation-item" key={citation.id ?? `${citation.sourceType}-${citation.sourceId}-${index}`}>
                    <span className="citation-index">{String(index + 1).padStart(2, "0")}</span>
                    <div className="citation-content">
                      <h3 className="citation-title">{citation.label ?? citation.sourceId}</h3>
                      <p className="citation-source">
                        {citation.sourceType.replaceAll("_", " ")} · {citation.sourceId}
                      </p>
                      {citation.quote && <blockquote className="citation-quote">“{citation.quote}”</blockquote>}
                      <dl className="citation-meta">
                        <dt>Locator</dt>
                        <dd>{locatorText(citation.locator)}</dd>
                        {citation.documentId && (
                          <>
                            <dt>Document</dt>
                            <dd>{citation.documentId}</dd>
                          </>
                        )}
                        {citation.chunkId && (
                          <>
                            <dt>Chunk</dt>
                            <dd>{citation.chunkId}</dd>
                          </>
                        )}
                      </dl>
                    </div>
                  </article>
                ))}
              </div>
            </aside>
          </div>,
          document.body
        )}
    </>
  );
}
