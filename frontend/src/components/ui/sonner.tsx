import { Toaster as Sonner } from "sonner";
import type { ComponentProps } from "react";

import { useTheme } from "@/app/providers/useTheme";

type ToasterProps = ComponentProps<typeof Sonner>;

/**
 * Thin wrapper around `sonner` so it follows the app's own ThemeProvider
 * instead of the OS-only preference sonner would otherwise read on its own.
 * Mounted once, globally, in AppProviders — any component anywhere can call
 * `toast(...)` (imported from "sonner") without needing its own Toaster.
 */
export function Toaster({ ...props }: ToasterProps) {
  const { resolvedTheme } = useTheme();

  return (
    <Sonner
      theme={resolvedTheme}
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
      {...props}
    />
  );
}
