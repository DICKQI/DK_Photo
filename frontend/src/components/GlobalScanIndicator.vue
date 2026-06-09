<template>
  <span
    v-if="visible && activeJobs.length > 0"
    class="scan-indicator"
  >
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
          <span class="scan-job-progress-group">
            <span class="scan-job-progress">{{ scanMediaProgressLabel(job) }}</span>
            <span v-if="scanCompactBreakdownLabel(job)" class="scan-job-detail">{{ scanCompactBreakdownLabel(job) }}</span>
          </span>
        </li>
      </ul>
    </div>
  </span>
</template>

<script setup lang="ts">
import { LoaderCircle } from 'lucide-vue-next';
import { useLocale } from '../composables/useLocale';
import { useScanJobs } from '../composables/useScanJobs';
import type { ScanJob } from '../types';

const { t } = useLocale();
const { activeJobs, visible } = useScanJobs();

function scanMediaProgressLabel(job: ScanJob) {
  if (job.total_estimated && job.total_estimated > 0) {
    return t('admin.scanMediaProgressTotal', { count: job.processed_assets.toLocaleString(), total: job.total_estimated.toLocaleString() });
  }
  return t('admin.scanMediaProgress', { count: job.processed_assets.toLocaleString() });
}

function scanCompactBreakdownLabel(job: ScanJob) {
  const parts: string[] = [];
  if (job.processed_images || job.total_estimated_images) {
    parts.push(t('admin.scanImageProgress', { count: job.processed_images.toLocaleString() }));
  }
  const thumbnailImageTotal = Math.max(job.processed_images, job.thumbnail_ready_images);
  if (thumbnailImageTotal > 0) {
    parts.push(t('admin.scanThumbnailReadyImages', { count: job.thumbnail_ready_images.toLocaleString(), total: thumbnailImageTotal.toLocaleString() }));
  }
  return parts.join(' · ');
}
</script>
