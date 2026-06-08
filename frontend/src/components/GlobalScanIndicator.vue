<template>
  <Teleport to="#scan-indicator-slot" v-if="visible && activeJobs.length > 0">
    <span class="scan-indicator">
      <button
        class="icon-button scan-indicator-trigger"
        type="button"
        :title="t('scan.indicatorTitle')"
      >
        <LoaderCircle class="spin" :size="18" />
        <span class="scan-indicator-badge">{{ activeJobs.length }}</span>
      </button>
      <div class="scan-indicator-popup">
        <div class="scan-indicator-popup-header">
          <strong>{{ t('scan.activeJobs') }}</strong>
        </div>
        <ul class="scan-indicator-list">
          <li v-for="job in activeJobs" :key="job.id" class="scan-indicator-job">
            <span class="scan-job-name">{{ job.library_name || `Library ${job.library_id}` }}</span>
            <span class="scan-job-progress">
              <template v-if="job.total_estimated && job.total_estimated > 0">
                {{ t('admin.scanningProgressTotal', { count: job.processed_assets.toLocaleString(), total: job.total_estimated.toLocaleString() }) }}
              </template>
              <template v-else>
                {{ t('admin.scanningProgress', { count: job.processed_assets.toLocaleString() }) }}
              </template>
            </span>
          </li>
        </ul>
      </div>
    </span>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { LoaderCircle } from 'lucide-vue-next';
import { useLocale } from '../composables/useLocale';
import { api } from '../services/api';
import type { ScanJob } from '../types';

const route = useRoute();
const { t } = useLocale();

const POLL_INTERVAL = 3000;
const activeJobs = ref<ScanJob[]>([]);
let pollTimer: ReturnType<typeof setInterval> | null = null;
let fetchGeneration = 0;

const visible = computed(() => Boolean(route.meta.requiresAuth));

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
  if (!visible.value || pollTimer) return;
  pollTimer = setInterval(fetchActiveJobs, POLL_INTERVAL);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

watch(visible, (isVisible) => {
  if (isVisible) {
    fetchActiveJobs();
    startPolling();
  } else {
    stopPolling();
    fetchGeneration++;
    activeJobs.value = [];
  }
});

onMounted(() => {
  if (visible.value) {
    fetchActiveJobs();
    startPolling();
  }
});

onUnmounted(() => {
  stopPolling();
});
</script>
