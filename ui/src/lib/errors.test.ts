import { describe, expect, it } from 'vitest'
import { ApiError, classifyError, type ErrorCategory } from './errors'

describe('classifyError', () => {
  it('classifies 401 as unauthorized', () => {
    const err = new ApiError('unauthorized', { status: 401 })
    const cat: ErrorCategory = classifyError(err)
    expect(cat.kind).toBe('unauthorized')
    expect(cat.status).toBe(401)
    expect(cat.message).toBe('unauthorized')
    expect(cat.fieldErrors).toBeNull()
    expect(cat.shouldToast).toBe(false)
  })

  it('classifies 422 with field errors as validation', () => {
    const err = new ApiError('invalid', {
      status: 422,
      body: {
        detail: [
          { loc: ['body', 'title'], msg: 'required', type: 'missing' },
          { loc: ['body', 'severity'], msg: 'bad value', type: 'value_error' },
        ],
      },
    })
    const cat = classifyError(err)
    expect(cat.kind).toBe('validation')
    expect(cat.status).toBe(422)
    expect(cat.fieldErrors).toEqual({
      title: 'required',
      severity: 'bad value',
    })
  })

  it('classifies 422 with string detail as validation with form-wide error', () => {
    const err = new ApiError('Bad input', {
      status: 422,
      body: { detail: 'Bad input' },
    })
    const cat = classifyError(err)
    expect(cat.kind).toBe('validation')
    expect(cat.fieldErrors).toEqual({ _form: 'Bad input' })
  })

  it('classifies 500 as server', () => {
    const err = new ApiError('boom', { status: 500 })
    expect(classifyError(err).kind).toBe('server')
  })

  it('classifies 503 as server', () => {
    const err = new ApiError('down', { status: 503 })
    expect(classifyError(err).kind).toBe('server')
  })

  it('classifies network error (no status) as network', () => {
    const err = new ApiError('Network request failed', { status: 0, isNetworkError: true })
    expect(classifyError(err).kind).toBe('network')
  })

  it('classifies TypeError (fetch failure) as network', () => {
    const err = new TypeError('Failed to fetch')
    expect(classifyError(err).kind).toBe('network')
  })

  it('classifies 400 as client', () => {
    const err = new ApiError('bad', { status: 400 })
    expect(classifyError(err).kind).toBe('client')
  })

  it('classifies 404 as client', () => {
    const err = new ApiError('missing', { status: 404 })
    expect(classifyError(err).kind).toBe('client')
  })

  it('extracts detail string from body for message', () => {
    const err = new ApiError('500 Internal Server Error', {
      status: 500,
      body: { detail: 'database is unavailable' },
    })
    expect(classifyError(err).message).toBe('database is unavailable')
  })

  it('handles unknown errors', () => {
    const cat = classifyError(new Error('mystery'))
    expect(cat.kind).toBe('unknown')
    expect(cat.message).toBe('mystery')
  })

  it('should surface toast for server errors', () => {
    expect(classifyError(new ApiError('x', { status: 500 })).shouldToast).toBe(true)
  })

  it('should surface toast for network errors', () => {
    expect(classifyError(new ApiError('x', { status: 0, isNetworkError: true })).shouldToast).toBe(true)
  })

  it('should NOT surface toast for 401', () => {
    expect(classifyError(new ApiError('x', { status: 401 })).shouldToast).toBe(false)
  })

  it('should NOT surface toast for 422', () => {
    expect(classifyError(new ApiError('x', { status: 422 })).shouldToast).toBe(false)
  })
})
