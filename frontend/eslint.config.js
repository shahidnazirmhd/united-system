import js from "@eslint/js";
import prettierConfig from "eslint-config-prettier";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

// Flat config (ESLint 9) — the current standard for new Vite + React + TS
// projects. `prettierConfig` is applied LAST so it can switch off every
// stylistic rule Prettier already owns, keeping ESLint focused on
// correctness/quality and Prettier focused on formatting — the two tools
// are never fighting over the same rule.
export default tseslint.config(
  { ignores: ["dist", "coverage", "node_modules"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommendedTypeChecked],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        project: ["./tsconfig.app.json", "./tsconfig.node.json"],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
      "jsx-a11y": jsxA11y,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // Enterprise baseline: an unused import/variable is a real defect
      // (dead code, or a refactor that wasn't finished), not a style nit.
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      // Explicit `any` defeats the entire point of TypeScript strict mode;
      // allowed only via an explicit inline `eslint-disable` with a reason.
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/consistent-type-imports": [
        "warn",
        { prefer: "type-imports", fixStyle: "inline-type-imports" },
      ],
    },
  },
  {
    // shadcn/ui primitives co-locate a component with its `cva` variant
    // export (e.g. `export { buttonVariants }` alongside `Button`) — the
    // established upstream convention `npx shadcn@latest add <component>`
    // itself generates. Fighting that convention by splitting every
    // primitive into two files would make hand-added components
    // inconsistent with anything the CLI adds later, so this one rule is
    // relaxed for this folder only; the app's own components (everything
    // outside components/ui) are held to the stricter default above.
    files: ["src/components/ui/**/*.{ts,tsx}"],
    rules: {
      "react-refresh/only-export-components": "off",
      // These primitives forward `{...props}` (which includes `children`
      // whenever a consumer passes it) straight onto a DOM element like
      // `<h3 {...props} />` — jsx-a11y can't see through the spread to know
      // content will be there at render time, so it flags every one of
      // these as content-less. True in the generated source, never true in
      // practice once a real consumer supplies children.
      "jsx-a11y/heading-has-content": "off",
    },
  },
  {
    // Test files run under Vitest's globals (describe/it/expect) — declared
    // separately so the app-code config above doesn't need to know about
    // testing at all.
    files: ["**/*.test.{ts,tsx}", "src/test/**/*.{ts,tsx}"],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
  },
  {
    // Plain Node config/tooling files (no type-aware linting needed here).
    files: ["*.config.{ts,js}", "*.config.*.{ts,js}"],
    languageOptions: {
      globals: globals.node,
    },
  },
  prettierConfig,
);
