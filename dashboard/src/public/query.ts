import { useCallback, useSyncExternalStore } from 'react';
import schema from './schema.json';
import type { ErrorResponse } from './contract';

export type QueryState<T> =
  | { state: 'loading' }
  | { state: 'ready'; data: T }
  | { state: 'error'; message: string; retryable: boolean };
type Listener = () => void;
type RecordState = {
  snapshot: QueryState<unknown>;
  listeners: Set<Listener>;
  controller?: AbortController;
  request?: object;
  updated: number;
};

function conforms(value: unknown, definition: Record<string, unknown>): boolean {
  if (definition.$ref) {
    const name = String(definition.$ref).split('/').pop()!;
    return conforms(value, schema.$defs[name as keyof typeof schema.$defs]);
  }
  if (definition.anyOf) {
    return (definition.anyOf as Record<string, unknown>[]).some((d) => conforms(value, d));
  }
  if (definition.enum && !(definition.enum as unknown[]).includes(value)) return false;
  if ('const' in definition && value !== definition.const) return false;
  return conformsType(value, definition);
}
function conformsString(value: unknown, d: Record<string, unknown>) {
  if (typeof value !== 'string') return false;
  if (d.format !== 'date' && d.format !== 'date-time') return true;
  return /^\d{4}-\d{2}-\d{2}/.test(value) && Number.isFinite(Date.parse(value));
}
function conformsType(value: unknown, d: Record<string, unknown>): boolean {
  if (d.type === 'null') return value === null;
  if (d.type === 'string') return conformsString(value, d);
  if (d.type === 'boolean') return typeof value === 'boolean';
  if (d.type === 'number' || d.type === 'integer') {
    return (
      typeof value === 'number' &&
      Number.isFinite(value) &&
      (d.type !== 'integer' || Number.isInteger(value)) &&
      (d.minimum === undefined || value >= Number(d.minimum)) &&
      (d.maximum === undefined || value <= Number(d.maximum))
    );
  }
  if (d.type === 'array') {
    return (
      Array.isArray(value) && value.every((v) => conforms(v, d.items as Record<string, unknown>))
    );
  }
  if (d.type === 'object') {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
    const props = d.properties as Record<string, Record<string, unknown>>;
    const record = value as Record<string, unknown>;
    return (
      Object.keys(props).every((k) => k in record) &&
      Object.entries(record).every(([k, v]) => k in props && conforms(v, props[k]))
    );
  }
  return true;
}

class ApiFailure extends Error {
  constructor(
    message: string,
    readonly retryable: boolean,
  ) {
    super(message);
  }
}
export class QueryCache {
  private records = new Map<string, RecordState>();
  constructor(
    private transport: typeof fetch = (...args) => fetch(...args),
    private ttl = 60_000,
  ) {}
  private record(key: string): RecordState {
    let entry = this.records.get(key);
    if (!entry) {
      this.prune();
      entry = { snapshot: { state: 'loading' }, listeners: new Set(), updated: 0 };
      this.records.set(key, entry);
    }
    return entry;
  }
  private prune() {
    if (this.records.size < 100) return;
    for (const [key, entry] of this.records) {
      if (entry.listeners.size === 0 && !entry.controller) this.records.delete(key);
      if (this.records.size < 100) break;
    }
  }
  snapshot<T>(key: string): QueryState<T> {
    return this.record(key).snapshot as QueryState<T>;
  }
  subscribe(key: string, type: keyof typeof schema.$defs, listener: Listener) {
    const entry = this.record(key);
    entry.listeners.add(listener);
    if (entry.snapshot.state === 'loading' || Date.now() - entry.updated > this.ttl) {
      this.start(key, type, entry);
    }
    return () => {
      entry.listeners.delete(listener);
      // React StrictMode's immediate resubscription shares the request.
      queueMicrotask(() => {
        if (entry.listeners.size === 0 && entry.controller) {
          entry.request = undefined;
          entry.controller.abort();
          entry.controller = undefined;
          entry.snapshot = { state: 'loading' };
        }
      });
    };
  }
  retry(key: string, type: keyof typeof schema.$defs) {
    const entry = this.record(key);
    entry.controller?.abort();
    entry.request = undefined;
    entry.controller = undefined;
    this.start(key, type, entry);
  }
  private publish(entry: RecordState, snapshot: QueryState<unknown>) {
    entry.snapshot = snapshot;
    for (const listener of entry.listeners) listener();
  }
  private start(key: string, type: keyof typeof schema.$defs, entry: RecordState) {
    if (entry.controller) return;
    const controller = new AbortController();
    const request = {};
    entry.controller = controller;
    entry.request = request;
    this.publish(entry, { state: 'loading' });
    void this.request(key, type, controller.signal)
      .then((data) => {
        if (entry.request === request) this.publish(entry, { state: 'ready', data });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || entry.request !== request) return;
        const failure =
          error instanceof ApiFailure
            ? error
            : new ApiFailure('The API could not be reached. Please retry.', true);
        this.publish(entry, {
          state: 'error',
          message: failure.message,
          retryable: failure.retryable,
        });
      })
      .finally(() => {
        if (entry.request !== request) return;
        entry.controller = undefined;
        entry.updated = Date.now();
      });
  }
  private async request(key: string, type: keyof typeof schema.$defs, signal: AbortSignal) {
    const response = await this.transport(key, { signal, headers: { Accept: 'application/json' } });
    const body: unknown = await response.json();
    if (!response.ok) {
      if (conforms(body, schema.$defs.ErrorResponse)) {
        const { error } = body as ErrorResponse;
        throw new ApiFailure(error.message, error.retryable);
      }
      throw new ApiFailure('The API returned an error. Please retry.', response.status >= 500);
    }
    if (!conforms(body, schema.$defs[type])) {
      throw new ApiFailure('The API response could not be verified. Please retry.', true);
    }
    return body;
  }
}
export const cache = new QueryCache();
export function useQuery<T>(key: string, type: keyof typeof schema.$defs) {
  const subscribe = useCallback(
    (listener: Listener) => cache.subscribe(key, type, listener),
    [key, type],
  );
  const snapshot = useCallback(() => cache.snapshot<T>(key), [key]);
  const result = useSyncExternalStore(subscribe, snapshot);
  return { ...result, retry: () => cache.retry(key, type) };
}
