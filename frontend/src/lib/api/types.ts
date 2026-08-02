/**
 * Types mirroring the backend's standard response envelope exactly (see
 * ../../../../backend/shared_kernel/api/response.py and every *_API.md doc
 * in the repo root) — the frontend must never invent its own shape for
 * these, since every endpoint across every current and future module
 * (Employees, Leave, Approvals, ...) returns one of these two shapes.
 */
export interface ApiSuccessResponse<TData> {
  success: true;
  data: TData;
  meta?: PaginationMetaResponse;
}

export interface PaginationMetaResponse {
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: unknown;
}

export interface ApiErrorResponse {
  success: false;
  error: ApiErrorPayload;
}

export type ApiEnvelope<TData> = ApiSuccessResponse<TData> | ApiErrorResponse;

/**
 * The shape every module's paginated `list()` API function returns to its
 * own hooks, after unwrapping `ApiSuccessResponse`'s `data`/`meta` into one
 * object — introduced in Phase 12 once Employee, User, and Department list
 * screens all needed the identical `{items, meta}` pairing. Kept here
 * (foundation) rather than redefined per module, since it's a pure function
 * of the wire envelope every list endpoint already returns, not a
 * module-specific concept.
 */
export interface PagedResult<TItem> {
  items: TItem[];
  meta: PaginationMetaResponse;
}

interface ApiErrorOptions {
  code: string;
  message: string;
  status: number | null;
  details?: unknown;
}

/**
 * Normalized error type every httpClient call rejects with — regardless of
 * whether the failure was a backend-crafted `{success: false, error: {...}}`
 * envelope, a network failure, or something else entirely. Consuming code
 * (TanStack Query's `error`, a component's catch block) only ever needs to
 * handle this one type.
 */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number | null;
  readonly details?: unknown;

  constructor({ code, message, status, details }: ApiErrorOptions) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}
