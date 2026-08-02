import { useEffect, useState } from "react";

/**
 * Reactive `window.matchMedia` subscription. Layouts in this foundation
 * (Sidebar/DashboardLayout) handle responsiveness with Tailwind breakpoint
 * classes alone and don't need this, but any future module that must branch
 * its React logic (not just its CSS) on viewport size — e.g. rendering a
 * table on desktop vs. a card list on mobile — should use this rather than
 * hand-rolling a resize listener.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState<boolean>(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false,
  );

  useEffect(() => {
    const mediaQueryList = window.matchMedia(query);
    const listener = () => setMatches(mediaQueryList.matches);

    listener();
    mediaQueryList.addEventListener("change", listener);
    return () => mediaQueryList.removeEventListener("change", listener);
  }, [query]);

  return matches;
}
