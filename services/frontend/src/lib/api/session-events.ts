/** Notifies listeners when refresh fails and the session is truly gone. */

const listeners = new Set<() => void>();

export function onSessionExpired(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function emitSessionExpired(): void {
  for (const listener of listeners) {
    listener();
  }
}
