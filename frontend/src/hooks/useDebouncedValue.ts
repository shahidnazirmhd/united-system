import { useEffect, useState } from "react";

/**
 * Delays reflecting a fast-changing value (typically a search input's
 * `value`) until it's stopped changing for `delayMs`. First need in this
 * codebase as of Phase 12's Employee/User/Department list search boxes —
 * without it, every keystroke would fire a new list request.
 */
export function useDebouncedValue<TValue>(value: TValue, delayMs = 350): TValue {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timeout = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timeout);
  }, [value, delayMs]);

  return debounced;
}
