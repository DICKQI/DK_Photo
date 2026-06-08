import { computed, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { api } from '../services/api';
import type { ScanJob } from '../types';

const POLL_INTERVAL = 3000;
const activeJobs = ref<ScanJob[]>([]);
let pollTimer: ReturnType<typeof setInterval> | null = null;
let fetchGeneration = 0;
let consumerCount = 0;

async function fetchActiveJobs() {
  const gen = ++fetchGeneration;
  try {
    const jobs = await api.activeJobs();
    if (gen === fetchGeneration) {
      activeJobs.value = jobs;
    }
  } catch {
    if (gen === fetchGeneration) {
      activeJobs.value = [];
    }
  }
}

function startPolling() {
  if (pollTimer) return;
  fetchActiveJobs();
  pollTimer = setInterval(fetchActiveJobs, POLL_INTERVAL);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

export function useScanJobs() {
  const route = useRoute();
  const visible = computed(() => Boolean(route.meta.requiresAuth));

  consumerCount++;
  if (consumerCount === 1 && visible.value) {
    startPolling();
  }

  watch(visible, (isVisible) => {
    if (isVisible) {
      if (!pollTimer) {
        startPolling();
      }
    } else if (consumerCount <= 1) {
      stopPolling();
      fetchGeneration++;
      activeJobs.value = [];
    }
  });

  onUnmounted(() => {
    consumerCount--;
    if (consumerCount <= 0) {
      consumerCount = 0;
      stopPolling();
    }
  });

  return { activeJobs, visible };
}
