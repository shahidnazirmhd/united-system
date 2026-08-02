/**
 * Typed, defensive wrapper around `window.localStorage`. Defensive because
 * `localStorage` can throw (Safari private mode, storage quota exceeded,
 * disabled by an enterprise browser policy) — every call in this file
 * degrades to a no-op/`null` instead of crashing whatever called it.
 */
function isStorageAvailable(): boolean {
  try {
    const testKey = "__united_hrms_storage_test__";
    window.localStorage.setItem(testKey, testKey);
    window.localStorage.removeItem(testKey);
    return true;
  } catch {
    return false;
  }
}

export const storage = {
  get<TValue>(key: string): TValue | null {
    if (!isStorageAvailable()) return null;
    const raw = window.localStorage.getItem(key);
    if (raw === null) return null;
    try {
      return JSON.parse(raw) as TValue;
    } catch {
      return null;
    }
  },

  set<TValue>(key: string, value: TValue): void {
    if (!isStorageAvailable()) return;
    window.localStorage.setItem(key, JSON.stringify(value));
  },

  remove(key: string): void {
    if (!isStorageAvailable()) return;
    window.localStorage.removeItem(key);
  },
};
