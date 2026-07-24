import { useEffect, useRef } from "react";

export function useAutoFollow<T extends HTMLElement>(dependency: unknown) {
  const containerRef = useRef<T>(null);
  const frameRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const followBottom = () => {
      if (frameRef.current !== null) window.cancelAnimationFrame(frameRef.current);
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);

      const scroll = () => {
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const overflowY = window.getComputedStyle(container).overflowY;
        if (overflowY === "auto" || overflowY === "scroll") {
          container.scrollTo({
            top: container.scrollHeight,
            behavior: reducedMotion ? "auto" : "smooth",
          });
        } else {
          container.lastElementChild?.scrollIntoView({
            block: "end",
            inline: "nearest",
            behavior: reducedMotion ? "auto" : "smooth",
          });
        }
      };

      frameRef.current = window.requestAnimationFrame(() => {
        frameRef.current = window.requestAnimationFrame(scroll);
      });
      timerRef.current = window.setTimeout(scroll, 280);
    };

    const resizeObserver = new ResizeObserver(followBottom);
    Array.from(container.children).forEach((child) => resizeObserver.observe(child));

    const mutationObserver = new MutationObserver(() => {
      resizeObserver.disconnect();
      Array.from(container.children).forEach((child) => resizeObserver.observe(child));
      followBottom();
    });
    mutationObserver.observe(container, { childList: true, subtree: true, characterData: true });
    followBottom();

    return () => {
      resizeObserver.disconnect();
      mutationObserver.disconnect();
      if (frameRef.current !== null) window.cancelAnimationFrame(frameRef.current);
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, [dependency]);

  return containerRef;
}
