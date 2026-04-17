/**
 * Standardized API error handling for OpenSOAR UI.
 *
 * `ApiError` is thrown by `api.ts` wrappers whenever a fetch response is
 * non-2xx or the network transport itself fails. It carries the HTTP status,
 * the parsed response body (when JSON), and an `isNetworkError` flag so
 * callers and UI error handlers can route appropriately.
 *
 * `classifyError` reduces any thrown value to a single `ErrorCategory`
 * that downstream UI code can consume without knowing transport details.
 */

export interface ApiErrorInit {
  status: number
  body?: unknown
  isNetworkError?: boolean
}

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown
  readonly isNetworkError: boolean

  constructor(message: string, init: ApiErrorInit) {
    super(message)
    this.name = 'ApiError'
    this.status = init.status
    this.body = init.body
    this.isNetworkError = init.isNetworkError ?? false
  }
}

export type ErrorKind =
  | 'unauthorized'
  | 'validation'
  | 'client'
  | 'server'
  | 'network'
  | 'unknown'

export interface ErrorCategory {
  kind: ErrorKind
  status: number
  message: string
  fieldErrors: Record<string, string> | null
  shouldToast: boolean
}

interface PydanticValidationItem {
  loc?: Array<string | number>
  msg?: string
  type?: string
}

function isPydanticValidationList(value: unknown): value is PydanticValidationItem[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'object' && item !== null)
}

function extractFieldErrors(body: unknown): Record<string, string> | null {
  if (!body || typeof body !== 'object') return null
  const detail = (body as { detail?: unknown }).detail

  if (typeof detail === 'string') {
    return { _form: detail }
  }

  if (isPydanticValidationList(detail)) {
    const errors: Record<string, string> = {}
    for (const item of detail) {
      const loc = item.loc ?? []
      // Drop the first segment ("body"/"query"/etc) if present, keep the field name.
      const trimmed = loc[0] === 'body' || loc[0] === 'query' || loc[0] === 'path' ? loc.slice(1) : loc
      const key = trimmed.map(String).join('.') || '_form'
      if (item.msg) errors[key] = item.msg
    }
    return Object.keys(errors).length > 0 ? errors : null
  }

  return null
}

function extractMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.body && typeof err.body === 'object') {
    const detail = (err.body as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}

export function classifyError(err: unknown): ErrorCategory {
  // Network (thrown TypeError by fetch when offline/DNS/etc)
  if (err instanceof TypeError) {
    return {
      kind: 'network',
      status: 0,
      message: err.message || 'Network request failed',
      fieldErrors: null,
      shouldToast: true,
    }
  }

  if (err instanceof ApiError) {
    if (err.isNetworkError || err.status === 0) {
      return {
        kind: 'network',
        status: 0,
        message: extractMessage(err, 'Network request failed'),
        fieldErrors: null,
        shouldToast: true,
      }
    }
    if (err.status === 401) {
      return {
        kind: 'unauthorized',
        status: 401,
        message: extractMessage(err, 'Unauthorized'),
        fieldErrors: null,
        shouldToast: false,
      }
    }
    if (err.status === 422) {
      return {
        kind: 'validation',
        status: 422,
        message: extractMessage(err, 'Validation failed'),
        fieldErrors: extractFieldErrors(err.body),
        shouldToast: false,
      }
    }
    if (err.status >= 500) {
      return {
        kind: 'server',
        status: err.status,
        message: extractMessage(err, 'Server error'),
        fieldErrors: null,
        shouldToast: true,
      }
    }
    if (err.status >= 400) {
      return {
        kind: 'client',
        status: err.status,
        message: extractMessage(err, 'Request failed'),
        fieldErrors: null,
        shouldToast: true,
      }
    }
  }

  const message = err instanceof Error ? err.message : 'Unknown error'
  return {
    kind: 'unknown',
    status: 0,
    message,
    fieldErrors: null,
    shouldToast: true,
  }
}

/** Convenience predicate for the mass-import sites that only care about auth. */
export function isUnauthorized(err: unknown): boolean {
  return err instanceof ApiError && err.status === 401
}
