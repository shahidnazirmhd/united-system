import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/**
 * Top-level render-error safety net. Catches any error thrown during render
 * anywhere in the tree below it and renders `fallback` instead of leaving
 * the user with a blank white screen.
 *
 * A class component is required here — React has no hook equivalent of
 * `componentDidCatch`/`getDerivedStateFromError` yet. Route-level errors
 * (a page's own loader/action failing) are handled separately by
 * RouteErrorBoundary via React Router's `errorElement` mechanism; this
 * component exists only for truly unexpected render-time crashes anywhere
 * in the tree, including outside the router (e.g. inside a provider).
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.props.onError?.(error, errorInfo);
    if (import.meta.env.DEV) {
      console.error("ErrorBoundary caught an error:", error, errorInfo);
    }
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}
