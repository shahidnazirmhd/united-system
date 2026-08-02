import { z } from "zod";

/**
 * The ONLY file in the application allowed to read `import.meta.env`
 * directly. Every other file imports `env` from here instead — that gives
 * us one place that (a) validates every variable is actually present and
 * well-formed, failing fast with a clear error at startup rather than a
 * confusing runtime failure deep in some component, and (b) exposes a
 * clean, camelCase, typed shape instead of scattering `import.meta.env.VITE_*`
 * string lookups throughout the codebase.
 */
const envSchema = z.object({
  apiBaseUrl: z.string().url({ message: "VITE_API_BASE_URL must be a valid URL" }),
  appName: z.string().min(1),
  appEnv: z.enum(["development", "staging", "production"]),
  isDev: z.boolean(),
  isProd: z.boolean(),
});

function loadEnv() {
  const parsed = envSchema.safeParse({
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
    appName: import.meta.env.VITE_APP_NAME,
    appEnv: import.meta.env.VITE_APP_ENV,
    isDev: import.meta.env.DEV,
    isProd: import.meta.env.PROD,
  });

  if (!parsed.success) {
    const details = parsed.error.issues
      .map((issue) => `  - ${issue.path.join(".")}: ${issue.message}`)
      .join("\n");
    throw new Error(
      `Invalid environment configuration. Check your .env file against .env.example:\n${details}`,
    );
  }

  return parsed.data;
}

export const env = loadEnv();
export type Env = typeof env;
