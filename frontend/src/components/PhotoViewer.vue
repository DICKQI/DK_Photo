<template>
  <div class="viewer" :class="{ 'info-collapsed': !showInfo }" @keydown.esc="$emit('close')" tabindex="0" ref="viewerRef">
    <header class="viewer-bar">
      <button class="viewer-icon" @click="$emit('close')" :title="t('viewer.close')">
        <X :size="22" />
      </button>
      <div class="viewer-title">
        <strong>{{ current.filename }}</strong>
        <span>{{ metaText }}</span>
      </div>
      <div class="viewer-actions">
        <div class="viewer-action-group">
          <button class="viewer-icon" :disabled="zoom <= minZoom" @click="zoomOut" :title="t('viewer.zoomOut')">
            <ZoomOut :size="20" />
          </button>
          <span class="viewer-zoom-readout">{{ zoomPercent }}</span>
          <button class="viewer-icon" :disabled="zoom >= maxZoom" @click="zoomIn" :title="t('viewer.zoomIn')">
            <ZoomIn :size="20" />
          </button>
          <button class="viewer-icon" @click="resetZoom" :title="t('viewer.fitToScreen')">
            <RotateCcw :size="19" />
          </button>
        </div>
        <div class="viewer-action-group">
          <button class="viewer-icon" :class="{ active: showInfo }" @click="showInfo = !showInfo" :title="t('viewer.toggleInfo')">
            <PanelRight :size="20" />
          </button>
          <button v-if="canShare" class="viewer-icon" @click="$emit('share', current)" :title="t('common.share')">
            <Share2 :size="20" />
          </button>
          <a class="viewer-icon" :class="{ disabled: imageLoading || !!imageError }" :href="assetOriginalUrl(current)" target="_blank" :title="t('common.downloadOriginal')">
            <Download :size="20" />
          </a>
        </div>
      </div>
    </header>
    <button class="viewer-nav left" @click="previous" :title="t('viewer.previous')">
      <ChevronLeft :size="28" />
    </button>
    <div class="viewer-stage" :class="{ loading: imageLoading, failed: !!imageError }" @wheel.prevent="handleWheel">
      <div v-if="hasMultipleAssets" class="viewer-context previous">
        <span>{{ t('viewer.previous') }}</span>
        <strong>{{ previousAsset.filename }}</strong>
      </div>
      <div v-if="hasMultipleAssets" class="viewer-context next">
        <span>{{ t('viewer.next') }}</span>
        <strong>{{ nextAsset.filename }}</strong>
      </div>
      <div v-if="imageLoading" class="viewer-loading">
        <LoaderCircle class="spin" :size="26" />
        <span>{{ t('viewer.loadingOriginal') }}</span>
      </div>
      <div v-if="imageError" class="viewer-load-error">
        <ImageOff :size="32" />
        <strong>{{ t('viewer.unableLoadPhoto') }}</strong>
        <span>{{ imageError }}</span>
        <button class="secondary-button" @click="retryImage">
          <RefreshCw :size="17" />
          {{ t('common.retry') }}
        </button>
      </div>
      <img
        :key="imageKey"
        class="viewer-image"
        :class="{ zoomed: zoom > 1, loaded: !imageLoading && !imageError }"
        :src="assetOriginalUrl(current)"
        :alt="current.filename"
        :style="{ transform: `scale(${zoom})` }"
        @load="handleImageLoad"
        @error="handleImageError"
      />
    </div>
    <button class="viewer-nav right" @click="next" :title="t('viewer.next')">
      <ChevronRight :size="28" />
    </button>
    <div class="viewer-filmstrip" ref="filmstripRef">
      <button
        v-for="(asset, assetIndex) in assets"
        :key="asset.id"
        class="filmstrip-item"
        :class="{ active: assetIndex === index }"
        :title="asset.filename"
        @click="goTo(assetIndex)"
      >
        <img :src="assetThumbnailUrl(asset, 'small')" :alt="asset.filename" loading="lazy" />
      </button>
    </div>
    <div class="viewer-progress" aria-hidden="true">
      <span :style="{ width: progressPercent }"></span>
    </div>
    <aside class="info-panel">
      <div class="info-panel-header">
        <p class="eyebrow">{{ t('viewer.info') }}</p>
        <button class="viewer-icon compact" :title="t('viewer.hideInfo')" @click="showInfo = false">
          <X :size="16" />
        </button>
      </div>
      <dl>
        <dt>{{ t('viewer.file') }}</dt>
        <dd>{{ current.filename }}</dd>
        <dt>{{ t('viewer.dimensions') }}</dt>
        <dd>{{ current.width || '-' }} x {{ current.height || '-' }}</dd>
        <dt>{{ t('viewer.size') }}</dt>
        <dd>{{ formatBytes(current.size) }}</dd>
        <dt>{{ t('viewer.captured') }}</dt>
        <dd>{{ current.captured_at ? formatDateTime(current.captured_at) : '-' }}</dd>
        <dt>{{ t('viewer.updated') }}</dt>
        <dd>{{ formatDateTime(current.updated_at) }}</dd>
      </dl>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { ChevronLeft, ChevronRight, Download, ImageOff, LoaderCircle, PanelRight, RefreshCw, RotateCcw, Share2, X, ZoomIn, ZoomOut } from 'lucide-vue-next';
import { useLocale } from '../composables/useLocale';
import { originalUrl, thumbnailUrl } from '../services/api';
import type { Asset } from '../types';

const props = defineProps<{
  assets: Asset[];
  index: number;
  canShare?: boolean;
  originalUrlFor?: (asset: Asset) => string;
  thumbnailUrlFor?: (asset: Asset, size: string) => string;
}>();

const emit = defineEmits<{
  close: [];
  'update:index': [index: number];
  share: [asset: Asset];
}>();

const viewerRef = ref<HTMLElement | null>(null);
const filmstripRef = ref<HTMLElement | null>(null);
const { t, formatDateTime } = useLocale();
const showInfo = ref(true);
const current = computed(() => props.assets[props.index]);
const metaText = computed(() => `${props.index + 1} / ${props.assets.length}`);
const previousAsset = computed(() => props.assets[props.index === 0 ? props.assets.length - 1 : props.index - 1] ?? current.value);
const nextAsset = computed(() => props.assets[props.index === props.assets.length - 1 ? 0 : props.index + 1] ?? current.value);
const progressPercent = computed(() => `${props.assets.length ? ((props.index + 1) / props.assets.length) * 100 : 0}%`);
const hasMultipleAssets = computed(() => props.assets.length > 1);
const canShare = computed(() => props.canShare ?? true);
const minZoom = 0.75;
const maxZoom = 3;
const zoomStep = 0.25;
const zoom = ref(1);
const imageLoading = ref(true);
const imageError = ref('');
const imageRetry = ref(0);
const zoomPercent = computed(() => `${Math.round(zoom.value * 100)}%`);
const imageKey = computed(() => `${current.value.id}:${imageRetry.value}`);

watch(
  () => props.index,
  () => {
    resetZoom();
    resetImageState();
    nextTick(scrollActiveThumbnailIntoView);
  },
);

onMounted(() => {
  nextTick(() => viewerRef.value?.focus());
  window.addEventListener('keydown', handleKey);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKey);
});

function handleKey(event: KeyboardEvent) {
  if (event.key === 'ArrowLeft') previous();
  if (event.key === 'ArrowRight') next();
  if (event.key === 'Escape') emit('close');
  if (event.key === '+' || event.key === '=') zoomIn();
  if (event.key === '-') zoomOut();
  if (event.key === '0') resetZoom();
  if (event.key.toLowerCase() === 'i') showInfo.value = !showInfo.value;
}

function previous() {
  goTo(props.index === 0 ? props.assets.length - 1 : props.index - 1);
}

function next() {
  goTo(props.index === props.assets.length - 1 ? 0 : props.index + 1);
}

function goTo(index: number) {
  emit('update:index', index);
}

function clampZoom(value: number) {
  return Math.min(maxZoom, Math.max(minZoom, Number(value.toFixed(2))));
}

function zoomIn() {
  zoom.value = clampZoom(zoom.value + zoomStep);
}

function zoomOut() {
  zoom.value = clampZoom(zoom.value - zoomStep);
}

function resetZoom() {
  zoom.value = 1;
}

function resetImageState() {
  imageLoading.value = true;
  imageError.value = '';
}

function handleWheel(event: WheelEvent) {
  if (imageLoading.value || imageError.value) return;
  if (event.deltaY < 0) zoomIn();
  if (event.deltaY > 0) zoomOut();
}

function handleImageLoad() {
  imageLoading.value = false;
  imageError.value = '';
}

function handleImageError() {
  imageLoading.value = false;
  imageError.value = t('viewer.originalDisplayFailed');
}

function retryImage() {
  resetZoom();
  resetImageState();
  imageRetry.value += 1;
}

function scrollActiveThumbnailIntoView() {
  const container = filmstripRef.value;
  const active = container?.querySelector<HTMLElement>('.filmstrip-item.active');
  active?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
}

function assetOriginalUrl(asset: Asset) {
  return props.originalUrlFor?.(asset) ?? originalUrl(asset.id);
}

function assetThumbnailUrl(asset: Asset, size: string) {
  return props.thumbnailUrlFor?.(asset, size) ?? thumbnailUrl(asset.id, size);
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
</script>
