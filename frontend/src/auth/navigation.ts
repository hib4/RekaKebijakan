export function navigate(path: string, replace = false) {
  window.history[replace ? "replaceState" : "pushState"](null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function safeNext(value: string | null, fallback = "/dashboard") {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return fallback;
  try {
    const url = new URL(value, window.location.origin);
    return url.origin === window.location.origin
      ? `${url.pathname}${url.search}${url.hash}`
      : fallback;
  } catch {
    return fallback;
  }
}
