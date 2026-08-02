import { RouterProvider } from "react-router-dom";

import { router } from "@/app/router/routes";

export function AppRouter() {
  return <RouterProvider router={router} />;
}
