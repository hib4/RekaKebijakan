import { useEffect, useRef } from "react";

export function useAutoFollow<T extends HTMLElement>(
  dependency: unknown,
  options: { force?: boolean } = {},
) {
  const containerRef = useRef<T>(null);
  const frameRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const settleTimerRef = useRef<number | null>(null);
  const followingRef = useRef(true);
  const autoScrollingRef = useRef(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const updateFollowing = () => {
      if (autoScrollingRef.current) return;
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
      if (settleTimerRef.current !== null) window.clearTimeout(settleTimerRef.current);
      if (options.force) followingRef.current = true;
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      const settleToBottom = () => {
        if (autoScrollingRef.current && followingRef.current) {
          container.scrollTop = container.scrollHeight;
        }
      };

      const scroll = () => {
        if (!followingRef.current) return;
        const overflowY = window.getComputedStyle(container).overflowY;
        autoScrollingRef.current = true;
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
        settleTimerRef.current = window.setTimeout(() => {
          settleToBottom();
          window.setTimeout(settleToBottom, reducedMotion ? 0 : 360);
          window.setTimeout(() => {
            settleToBottom();
            autoScrollingRef.current = false;
            updateFollowing();
          }, reducedMotion ? 0 : 760);
        }, reducedMotion ? 0 : 420);
      };

      const delayedSettle = () => {
        window.setTimeout(() => {
          settleToBottom();
          autoScrollingRef.current = false;
          updateFollowing();
        }, reducedMotion ? 0 : 1180);
      };

      frameRef.current = window.requestAnimationFrame(() => {
        frameRef.current = window.requestAnimationFrame(scroll);
      });
      timerRef.current = window.setTimeout(() => {
        scroll();
        delayedSettle();
      }, 280);
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
      if (settleTimerRef.current !== null) window.clearTimeout(settleTimerRef.current);
    };
  }, [dependency, options.force]);

  return containerRef;
}
