import { useEffect, useRef } from "react";

export function useAutoFollow<T extends HTMLElement>(dependency: unknown) {
  const containerRef = useRef<T>(null);
  const frameRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const followingRef = useRef(true);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const updateFollowing = () => {
      const overflowY = window.getComputedStyle(container).overflowY;
      if (overflowY === "auto" || overflowY === "scroll") {
        followingRef.current = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
      }
    };
    const stopFollowingOnUpwardScroll = (event: WheelEvent) => {
      if (event.deltaY < 0) followingRef.current = false;
    };
    container.addEventListener("scroll", updateFollowing, { passive: true });
    container.addEventListener("wheel", stopFollowingOnUpwardScroll, { passive: true });

    const followBottom = () => {
      if (frameRef.current !== null) window.cancelAnimationFrame(frameRef.current);
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);

      const scroll = () => {
        if (!followingRef.current) return;
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
      container.removeEventListener("scroll", updateFollowing);
      container.removeEventListener("wheel", stopFollowingOnUpwardScroll);
      if (frameRef.current !== null) window.cancelAnimationFrame(frameRef.current);
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, [dependency]);

  return containerRef;
}
