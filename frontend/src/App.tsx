import { AppProviders } from "@/app/providers";
import { AppRouter } from "@/app/router";

/**
 * Application root. Deliberately just a composition of the two things every
 * app needs — global providers and the router — so it never grows business
 * logic of its own. Anything else belongs in app/providers, app/router,
 * layouts, or a feature module under src/modules.
 */
export function App() {
  return (
    <AppProviders>
      <AppRouter />
    </AppProviders>
  );
}
