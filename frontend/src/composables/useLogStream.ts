import { computed, ref } from 'vue';
import { logStreamUrl } from '../services/api';
import type { LogEntry } from '../types';

export type LogStreamStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error';

const DEFAULT_TAIL = 200;
const DEFAULT_MAX_ENTRIES = 2000;
const DEFAULT_RETRY_DELAYS_MS = [500, 1000, 2000, 5000];

interface UseLogStreamOptions {
  tail?: number;
  maxEntries?: number;
  retryDelaysMs?: number[];
}

export function useLogStream(options: UseLogStreamOptions = {}) {
  const tail = options.tail ?? DEFAULT_TAIL;
  const maxEntries = options.maxEntries ?? DEFAULT_MAX_ENTRIES;
  const retryDelaysMs = options.retryDelaysMs?.length ? options.retryDelaysMs : DEFAULT_RETRY_DELAYS_MS;

  const logs = ref<LogEntry[]>([]);
  const status = ref<LogStreamStatus>('disconnected');
  const connected = computed(() => status.value === 'connected');

  let eventSource: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let retryAttempt = 0;
  let lastSeenId: number | null = null;
  let manuallyClosed = false;

  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function streamUrl() {
    if (lastSeenId !== null) {
      return logStreamUrl({ tail: 0, after: lastSeenId });
    }
    return logStreamUrl({ tail });
  }

  function appendEntry(entry: LogEntry) {
    logs.value.push(entry);
    if (logs.value.length > maxEntries) {
      logs.value.splice(0, logs.value.length - maxEntries);
    }
    if (typeof entry.id === 'number') {
      lastSeenId = Math.max(lastSeenId ?? 0, entry.id);
    }
  }

  function scheduleReconnect(source: EventSource) {
    if (reconnectTimer || manuallyClosed) return;
    source.close();
    if (eventSource === source) {
      eventSource = null;
    }
    status.value = 'reconnecting';
    const delay = retryDelaysMs[Math.min(retryAttempt, retryDelaysMs.length - 1)];
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      retryAttempt += 1;
      connect();
    }, delay);
  }

  function connect() {
    manuallyClosed = false;
    clearReconnectTimer();
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }

    status.value = lastSeenId === null ? 'connecting' : 'reconnecting';
    let source: EventSource;
    try {
      source = new EventSource(streamUrl(), { withCredentials: true });
    } catch {
      status.value = 'error';
      return;
    }
    eventSource = source;

    const markConnected = () => {
      if (eventSource !== source) return;
      status.value = 'connected';
      retryAttempt = 0;
    };

    source.onopen = markConnected;
    source.addEventListener('ready', markConnected);
    source.onmessage = (event) => {
      if (eventSource !== source) return;
      try {
        appendEntry(JSON.parse(event.data) as LogEntry);
      } catch {
      }
    };
    source.onerror = () => {
      if (eventSource !== source) return;
      scheduleReconnect(source);
    };
  }

  function disconnect() {
    manuallyClosed = true;
    clearReconnectTimer();
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    status.value = 'disconnected';
  }

  function clearLogs() {
    logs.value = [];
  }

  return {
    logs,
    status,
    connected,
    connect,
    disconnect,
    clearLogs,
  };
}
