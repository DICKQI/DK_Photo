import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useLogStream } from './useLogStream';

type Listener = (event: MessageEvent<string>) => void;

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  url: string;
  withCredentials: boolean;
  onopen: (() => void) | null = null;
  onmessage: Listener | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();
  private listeners = new Map<string, Listener[]>();

  constructor(url: string, init?: EventSourceInit) {
    this.url = url;
    this.withCredentials = Boolean(init?.withCredentials);
    FakeEventSource.instances.push(this);
  }

  addEventListener(event: string, listener: Listener) {
    const listeners = this.listeners.get(event) ?? [];
    listeners.push(listener);
    this.listeners.set(event, listeners);
  }

  emitReady() {
    this.listeners.get('ready')?.forEach((listener) => listener({ data: '{"connected":true}' } as MessageEvent<string>));
  }

  emitMessage(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
  }

  emitError() {
    this.onerror?.();
  }
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal('EventSource', FakeEventSource);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('useLogStream', () => {
  it('marks the stream connected as soon as ready arrives', () => {
    const stream = useLogStream({ retryDelaysMs: [500], maxEntries: 3 });

    stream.connect();

    const source = FakeEventSource.instances[0];
    expect(source.url).toBe('/api/admin/logs/stream?tail=200');
    expect(source.withCredentials).toBe(true);
    expect(stream.status.value).toBe('connecting');

    source.emitReady();

    expect(stream.status.value).toBe('connected');
    expect(stream.connected.value).toBe(true);
  });

  it('appends log messages, trims old entries, and reconnects after the last seen id', () => {
    vi.useFakeTimers();
    const stream = useLogStream({ retryDelaysMs: [500], maxEntries: 2 });
    stream.connect();
    const source = FakeEventSource.instances[0];
    source.emitReady();

    source.emitMessage({ id: 1, timestamp: 't1', level: 'INFO', logger: 'tests', message: 'first' });
    source.emitMessage({ id: 2, timestamp: 't2', level: 'INFO', logger: 'tests', message: 'second' });
    source.emitMessage({ id: 3, timestamp: 't3', level: 'ERROR', logger: 'tests', message: 'third' });

    expect(stream.logs.value.map((entry) => entry.message)).toEqual(['second', 'third']);

    source.emitError();
    source.emitError();
    expect(stream.status.value).toBe('reconnecting');
    expect(source.close).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(500);

    expect(FakeEventSource.instances).toHaveLength(2);
    expect(FakeEventSource.instances[1].url).toBe('/api/admin/logs/stream?tail=0&after=3');
  });

  it('disconnect closes the active source and cancels pending reconnects', () => {
    vi.useFakeTimers();
    const stream = useLogStream({ retryDelaysMs: [500], maxEntries: 3 });
    stream.connect();
    const source = FakeEventSource.instances[0];

    source.emitError();
    stream.disconnect();
    vi.advanceTimersByTime(500);

    expect(source.close).toHaveBeenCalledTimes(1);
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(stream.status.value).toBe('disconnected');
  });

  it('marks the stream as error when EventSource cannot be created', () => {
    vi.stubGlobal(
      'EventSource',
      class {
        constructor() {
          throw new Error('EventSource unavailable');
        }
      },
    );
    const stream = useLogStream({ retryDelaysMs: [500], maxEntries: 3 });

    stream.connect();

    expect(stream.status.value).toBe('error');
  });
});
