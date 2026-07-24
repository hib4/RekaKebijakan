let currentNamespace = "anonymous";

export function setAuthStorageNamespace(userId: string | null) {
  currentNamespace = userId ? encodeURIComponent(userId) : "anonymous";
}

export function authStorageKey(key: string) {
  return `${key}:${currentNamespace}`;
}
