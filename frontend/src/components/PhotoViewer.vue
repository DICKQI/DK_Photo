<template>
  <div
    class="viewer"
    :class="{ 'info-collapsed': !showInfo, 'filmstrip-expanded': filmstripExpanded }"
    @keydown.esc="$emit('close')"
    tabindex="0"
    ref="viewerRef"
  >
    <header class="viewer-bar">
      <button class="viewer-icon" @click="$emit('close')" :title="t('viewer.close')">
        <X :size="22" />
      </button>
      <div class="viewer-title">
        <strong>{{ current.filename }}</strong>
        <span>{{ metaText }}</span>
      </div>
      <div class="viewer-actions">
        <div v-if="!isVideo" class="viewer-action-group">
          <button class="viewer-icon" :disabled="zoom <= minZoom" @click="zoomOut" :title="t('viewer.zoomOut')">
            <ZoomOut :size="20" />
          </button>
          <span class="viewer-zoom-readout">{{ zoomPercent }}</span>
          <button class="viewer-icon" :disabled="zoom >= maxZoom" @click="zoomIn" :title="t('viewer.zoomIn')">
            <ZoomIn :size="20" />
          </button>
          <button class="viewer-icon" @click="resetZoom" :title="t('viewer.fitToScreen')">
            <Maximize2 :size="19" />
          </button>
          <button class="viewer-icon" @click="rotateLeft" :title="t('viewer.rotateLeft')">
            <RotateCcw :size="19" />
          </button>
          <button class="viewer-icon" @click="rotateRight" :title="t('viewer.rotateRight')">
            <RotateCw :size="19" />
          </button>
        </div>
        <div class="viewer-action-group">
          <button
            v-if="hasMultipleAssets"
            class="viewer-icon"
            :class="{ active: slideshowPlaying }"
            @click="toggleSlideshow"
            :title="slideshowPlaying ? t('viewer.pauseSlideshow') : t('viewer.startSlideshow')"
          >
            <Pause v-if="slideshowPlaying" :size="20" />
            <Play v-else :size="20" />
          </button>
          <button class="viewer-icon" :class="{ active: showInfo }" @click="showInfo = !showInfo" :title="t('viewer.toggleInfo')">
            <PanelRight :size="20" />
          </button>
          <button
            v-if="canFavorite"
            class="viewer-icon favorite-icon"
            :class="{ active: current.is_favorite }"
            @click="$emit('favorite', current)"
            :title="current.is_favorite ? t('album.removeFavorite') : t('album.addFavorite')"
          >
            <Star :size="20" />
          </button>
          <button
            v-if="canAddToAlbum"
            class="viewer-icon"
            @click="$emit('add-to-album', current)"
            :title="t('album.addToAlbum')"
          >
            <ImagePlus :size="20" />
          </button>
          <button
            v-if="canSetAlbumCover"
            class="viewer-icon album-cover-icon"
            :class="{ active: albumCoverActive }"
            @click="$emit('set-album-cover', current)"
            :title="albumCoverActive ? t('album.currentCover') : t('album.setAlbumCover')"
          >
            <Images :size="20" />
          </button>
          <button
            v-if="canRemoveFromAlbum"
            class="viewer-icon danger-icon"
            :disabled="albumActionBusy"
            @click="$emit('remove-from-album', current)"
            :title="t('album.removeFromAlbum')"
          >
            <LoaderCircle v-if="albumActionBusy" class="spin" :size="20" />
            <ImageMinus v-else :size="20" />
          </button>
          <button v-if="canShare" class="viewer-icon" @click="$emit('share', current)" :title="t('common.share')">
            <Share2 :size="20" />
          </button>
          <button class="viewer-icon" :disabled="mediaLoading || !!mediaError || downloading" @click="downloadCurrent" :title="t('common.downloadOriginal')">
            <LoaderCircle v-if="downloading" class="spin" :size="20" />
            <Download v-else :size="20" />
          </button>
        </div>
      </div>
    </header>
    <button class="viewer-nav left" @click="previous" :title="t('viewer.previous')">
      <ChevronLeft :size="28" />
    </button>
    <div
      ref="stageRef"
      class="viewer-stage"
      :class="{ loading: mediaLoading, failed: !!mediaError, zoomed: !isVideo && zoom > 1 }"
      @wheel.prevent="handleWheel"
      @touchstart="handleTouchStart"
      @touchend="handleTouchEnd"
      @touchcancel="cancelTouch"
    >
      <div v-if="hasMultipleAssets" class="viewer-context previous">
        <span>{{ t('viewer.previous') }}</span>
        <strong>{{ previousAsset.filename }}</strong>
      </div>
      <div v-if="hasMultipleAssets" class="viewer-context next">
        <span>{{ t('viewer.next') }}</span>
        <strong>{{ nextAsset.filename }}</strong>
      </div>
      <div v-if="mediaLoading" class="viewer-loading">
        <LoaderCircle class="spin" :size="26" />
        <span>{{ isVideo ? t('viewer.loadingVideo') : t('viewer.loadingOriginal') }}</span>
      </div>
      <div v-if="mediaError" class="viewer-load-error">
        <ImageOff :size="32" />
        <strong>{{ isVideo ? t('viewer.unableLoadVideo') : t('viewer.unableLoadPhoto') }}</strong>
        <span>{{ mediaError }}</span>
        <button class="secondary-button" @click="retryMedia">
          <RefreshCw :size="17" />
          {{ t('common.retry') }}
        </button>
      </div>
      <div v-if="isVideo" class="viewer-video-frame">
        <video
          :key="mediaKey"
          class="viewer-video"
          :class="{ loaded: !mediaLoading && !mediaError }"
          :src="assetOriginalUrl(current)"
          :poster="assetThumbnailUrl(current, 'large')"
          controls
          playsinline
          preload="metadata"
          @loadedmetadata="handleVideoLoad"
          @canplay="handleVideoLoad"
          @error="handleMediaError"
        />
      </div>
      <div v-else class="viewer-image-frame" :style="imageFrameStyle">
        <div class="viewer-image-rotator" :style="imageRotatorStyle">
          <img
            :key="mediaKey"
            class="viewer-image"
            :class="{ zoomed: zoom > 1, loaded: !mediaLoading && !mediaError }"
            :src="assetOriginalUrl(current)"
            :alt="current.filename"
            :style="imageStyle"
            @load="handleImageLoad"
            @error="handleMediaError"
          />
        </div>
      </div>
    </div>
    <button class="viewer-nav right" @click="next" :title="t('viewer.next')">
      <ChevronRight :size="28" />
    </button>
    <div class="viewer-filmstrip" :class="{ expanded: filmstripExpanded }">
      <div class="viewer-filmstrip-summary">
        <span class="viewer-filmstrip-status">{{ metaText }}</span>
        <button
          v-if="hasMultipleAssets"
          class="viewer-icon compact filmstrip-toggle"
          :class="{ active: filmstripExpanded }"
          type="button"
          :title="filmstripExpanded ? t('viewer.hidePreviewStrip') : t('viewer.showPreviewStrip')"
          :aria-label="filmstripExpanded ? t('viewer.hidePreviewStrip') : t('viewer.showPreviewStrip')"
          :aria-expanded="filmstripExpanded"
          @click="toggleFilmstrip"
        >
          <Images :size="16" />
        </button>
      </div>
      <template v-if="filmstripExpanded">
        <div
          class="viewer-filmstrip-track"
          :class="{ dragging: filmstripDragging, scrollable: filmstripScrollable }"
          ref="filmstripRef"
          @scroll="updateFilmstripScroll"
          @pointerdown="handleFilmstripPointerDown"
          @pointermove="handleFilmstripPointerMove"
          @pointerup="endFilmstripDrag"
          @pointerleave="endFilmstripDrag"
          @pointercancel="endFilmstripDrag"
        >
          <button
            v-for="(asset, assetIndex) in assets"
            :key="asset.id"
            class="filmstrip-item"
            :class="{ active: assetIndex === index }"
            type="button"
            :title="asset.filename"
            :data-filmstrip-index="assetIndex"
            @click="handleFilmstripItemClick(assetIndex, $event)"
          >
            <img :src="assetThumbnailUrl(asset, 'small')" :alt="asset.filename" loading="lazy" decoding="async" />
          </button>
        </div>
        <input
          v-if="filmstripScrollable"
          class="filmstrip-scrollbar"
          type="range"
          min="0"
          :max="filmstripScrollMax"
          step="1"
          :value="filmstripScrollLeft"
          :aria-label="t('viewer.previewStripScroll')"
          @input="handleFilmstripScrollbarInput"
        />
      </template>
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
        <template v-if="sourceLabel">
          <dt>{{ t('viewer.location') }}</dt>
          <dd class="info-source">
            <span>{{ sourceLabel }}</span>
            <button v-if="canLocate" class="info-source-button" :title="t('album.openContainingFolder')" @click="$emit('locate', current)">
              <FolderOpen :size="15" />
              {{ t('album.openContainingFolder') }}
            </button>
          </dd>
        </template>
        <template v-if="coordinateLabel">
          <dt>{{ t('viewer.coordinates') }}</dt>
          <dd class="info-source">
            <span>{{ coordinateLabel }}</span>
            <a class="info-source-button" :href="mapUrl" target="_blank" rel="noreferrer" :title="t('viewer.openMap')">
              <MapPin :size="15" />
              {{ t('viewer.openMap') }}
            </a>
          </dd>
        </template>
        <dt>{{ t('viewer.dimensions') }}</dt>
        <dd>{{ current.width || '-' }} x {{ current.height || '-' }}</dd>
        <dt>{{ t('viewer.type') }}</dt>
        <dd>{{ mediaTypeLabel }}</dd>
        <dt>{{ t('viewer.size') }}</dt>
        <dd>{{ formatBytes(current.size) }}</dd>
        <dt>{{ t('viewer.captured') }}</dt>
        <dd>{{ current.captured_at ? formatDateTime(current.captured_at) : '-' }}</dd>
        <template v-if="cameraLabel">
          <dt>{{ t('viewer.camera') }}</dt>
          <dd>{{ cameraLabel }}</dd>
        </template>
        <template v-if="current.lens_model">
          <dt>{{ t('viewer.lens') }}</dt>
          <dd>{{ current.lens_model }}</dd>
        </template>
        <template v-if="exposureLabel">
          <dt>{{ t('viewer.exposure') }}</dt>
          <dd>{{ exposureLabel }}</dd>
        </template>
        <dt>{{ t('viewer.rating') }}</dt>
        <dd class="info-rating">
          <div class="rating-control" :aria-label="t('viewer.rating')">
            <button
              v-for="value in ratingOptions"
              :key="value"
              class="rating-star-button"
              :class="{ active: value <= currentRating }"
              :disabled="!canEditMetadata"
              :title="t('viewer.setRating', { rating: value })"
              @click="setRating(value)"
            >
              <Star :size="17" :fill="value <= currentRating ? 'currentColor' : 'none'" />
            </button>
            <button
              v-if="canEditMetadata && currentRating > 0"
              class="viewer-icon compact"
              type="button"
              :title="t('viewer.clearRating')"
              @click="setRating(0)"
            >
              <X :size="15" />
            </button>
          </div>
          <small>{{ currentRating ? t('viewer.ratingValue', { rating: currentRating }) : t('viewer.unrated') }}</small>
        </dd>
        <dt>{{ t('viewer.description') }}</dt>
        <dd class="info-description">
          <form v-if="descriptionEditing" class="metadata-editor" @submit.prevent="saveDescription">
            <textarea
              ref="descriptionInputRef"
              v-model="descriptionInput"
              maxlength="2000"
              rows="4"
              :placeholder="t('viewer.descriptionPlaceholder')"
            ></textarea>
            <div class="tag-editor-actions">
              <button class="viewer-icon compact" type="submit" :title="t('viewer.saveDescription')">
                <Save :size="15" />
              </button>
              <button class="viewer-icon compact" type="button" :title="t('common.cancel')" @click="cancelDescriptionEdit">
                <X :size="15" />
              </button>
            </div>
          </form>
          <div v-else class="description-summary">
            <p :class="{ empty: !currentDescription }">{{ currentDescription || t('viewer.noDescription') }}</p>
            <button v-if="canEditMetadata" class="viewer-icon compact" :title="t('viewer.editDescription')" @click="beginDescriptionEdit">
              <Pencil :size="15" />
            </button>
          </div>
        </dd>
        <dt>{{ t('viewer.tags') }}</dt>
        <dd class="info-tags">
          <form v-if="tagEditing" class="tag-editor" @submit.prevent="saveTags">
            <input
              ref="tagInputRef"
              v-model="tagInput"
              type="text"
              :placeholder="t('viewer.tagsPlaceholder')"
            />
            <div class="tag-editor-actions">
              <button class="viewer-icon compact" type="submit" :title="t('viewer.saveTags')">
                <Save :size="15" />
              </button>
              <button class="viewer-icon compact" type="button" :title="t('common.cancel')" @click="cancelTagEdit">
                <X :size="15" />
              </button>
            </div>
          </form>
          <div v-else class="tag-summary">
            <div class="tag-pills" :class="{ empty: !currentTags.length }">
              <template v-if="currentTags.length">
                <span v-for="tag in currentTags" :key="tag" class="tag-pill">{{ tag }}</span>
              </template>
              <span v-else>{{ t('viewer.noTags') }}</span>
            </div>
            <button v-if="canEditTags" class="viewer-icon compact" :title="t('viewer.editTags')" @click="beginTagEdit">
              <Tag :size="15" />
            </button>
          </div>
        </dd>
        <dt>{{ t('viewer.updated') }}</dt>
        <dd>{{ formatDateTime(current.updated_at) }}</dd>
      </dl>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  ChevronLeft,
  ChevronRight,
  Download,
  FolderOpen,
  ImageMinus,
  ImageOff,
  ImagePlus,
  Images,
  LoaderCircle,
  MapPin,
  Maximize2,
  PanelRight,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  RotateCcw,
  RotateCw,
  Save,
  Share2,
  Star,
  Tag,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-vue-next';
import { useLocale } from '../composables/useLocale';
import { downloadUrl, originalUrl, thumbnailUrl } from '../services/api';
import type { Asset } from '../types';

const props = defineProps<{
  assets: Asset[];
  index: number;
  canShare?: boolean;
  canFavorite?: boolean;
  canLocate?: boolean;
  canEditTags?: boolean;
  canEditMetadata?: boolean;
  canAddToAlbum?: boolean;
  canSetAlbumCover?: boolean;
  canRemoveFromAlbum?: boolean;
  albumCoverAssetId?: number | null;
  albumActionBusy?: boolean;
  shortcutsDisabled?: boolean;
  originalUrlFor?: (asset: Asset) => string;
  thumbnailUrlFor?: (asset: Asset, size: string) => string;
}>();

const emit = defineEmits<{
  close: [];
  'update:index': [index: number];
  share: [asset: Asset];
  favorite: [asset: Asset];
  locate: [asset: Asset];
  'add-to-album': [asset: Asset];
  'set-album-cover': [asset: Asset];
  'remove-from-album': [asset: Asset];
  'update-tags': [asset: Asset, tags: string[]];
  'update-metadata': [asset: Asset, metadata: { description: string; rating: number }];
  downloaded: [asset: Asset];
  downloadError: [message: string];
}>();

const viewerRef = ref<HTMLElement | null>(null);
const stageRef = ref<HTMLElement | null>(null);
const filmstripRef = ref<HTMLElement | null>(null);
const { t, formatDateTime } = useLocale();
const showInfo = ref(typeof window !== 'undefined' ? window.innerWidth > 900 : true);
const current = computed(() => props.assets[props.index]);
const metaText = computed(() => `${props.index + 1} / ${props.assets.length}`);
const previousAsset = computed(() => props.assets[props.index === 0 ? props.assets.length - 1 : props.index - 1] ?? current.value);
const nextAsset = computed(() => props.assets[props.index === props.assets.length - 1 ? 0 : props.index + 1] ?? current.value);
const progressPercent = computed(() => `${props.assets.length ? ((props.index + 1) / props.assets.length) * 100 : 0}%`);
const hasMultipleAssets = computed(() => props.assets.length > 1);
const canShare = computed(() => props.canShare ?? true);
const canFavorite = computed(() => props.canFavorite ?? true);
const canLocate = computed(() => props.canLocate ?? true);
const canEditTags = computed(() => props.canEditTags ?? false);
const canEditMetadata = computed(() => props.canEditMetadata ?? false);
const canAddToAlbum = computed(() => props.canAddToAlbum ?? false);
const canSetAlbumCover = computed(() => props.canSetAlbumCover ?? false);
const canRemoveFromAlbum = computed(() => props.canRemoveFromAlbum ?? false);
const albumActionBusy = computed(() => props.albumActionBusy ?? false);
const albumCoverActive = computed(() => props.albumCoverAssetId === current.value.id);
const sourceLabel = computed(() => assetSourceLabel(current.value));
const coordinateLabel = computed(() => assetCoordinateLabel(current.value));
const mapUrl = computed(() => {
  const latitude = current.value.latitude;
  const longitude = current.value.longitude;
  return typeof latitude === 'number' && typeof longitude === 'number' ? `https://www.google.com/maps?q=${latitude},${longitude}` : '#';
});
const cameraLabel = computed(() => [current.value.camera_make, current.value.camera_model].filter(Boolean).join(' '));
const isVideo = computed(() => current.value.mime_type.startsWith('video/'));
const mediaTypeLabel = computed(() => (isVideo.value ? t('album.videoAsset') : t('common.photos')));
const exposureLabel = computed(() =>
  [current.value.aperture, current.value.exposure_time, current.value.focal_length, current.value.iso ? `ISO ${current.value.iso}` : ''].filter(Boolean).join(' / '),
);
const minZoom = 0.75;
const maxZoom = 3;
const zoomStep = 0.25;
const zoom = ref(1);
const rotation = ref(0);
const mediaLoading = ref(true);
const mediaError = ref('');
const mediaRetry = ref(0);
const downloading = ref(false);
const slideshowPlaying = ref(false);
const filmstripExpanded = ref(false);
const filmstripScrollLeft = ref(0);
const filmstripScrollMax = ref(0);
const filmstripDragging = ref(false);
const filmstripDragMoved = ref(false);
const filmstripDragStartX = ref(0);
const filmstripDragStartScrollLeft = ref(0);
const filmstripPointerDownIndex = ref<number | null>(null);
const filmstripSuppressClick = ref(false);
const filmstripScrollable = computed(() => filmstripScrollMax.value > 0);
const touchStartX = ref(0);
const touchStartY = ref(0);
const touchActive = ref(false);
const minSwipeDistance = 50;
const tagEditing = ref(false);
const tagInput = ref('');
const tagInputRef = ref<HTMLInputElement | null>(null);
const currentTags = computed(() => current.value.tags ?? []);
const descriptionEditing = ref(false);
const descriptionInput = ref('');
const descriptionInputRef = ref<HTMLTextAreaElement | null>(null);
const ratingOptions = [1, 2, 3, 4, 5];
const currentDescription = computed(() => current.value.description?.trim() ?? '');
const currentRating = computed(() => normalizeRating(current.value.rating));
const stageSize = ref({ width: 1, height: 1 });
const imageNaturalSize = ref(assetImageSize(current.value));
const zoomPercent = computed(() => `${Math.round(zoom.value * 100)}%`);
const mediaKey = computed(() => `${current.value.id}:${mediaRetry.value}`);
const rotatedSideways = computed(() => rotation.value === 90 || rotation.value === 270);
const fittedImageSize = computed(() => {
  const naturalWidth = Math.max(1, imageNaturalSize.value.width);
  const naturalHeight = Math.max(1, imageNaturalSize.value.height);
  const displayNaturalWidth = rotatedSideways.value ? naturalHeight : naturalWidth;
  const displayNaturalHeight = rotatedSideways.value ? naturalWidth : naturalHeight;
  const stageWidth = Math.max(1, stageSize.value.width);
  const stageHeight = Math.max(1, stageSize.value.height);
  const fitScale = Math.min(stageWidth / displayNaturalWidth, stageHeight / displayNaturalHeight);
  const safeFitScale = Number.isFinite(fitScale) && fitScale > 0 ? fitScale : 1;
  const imageWidth = Math.max(1, Math.round(naturalWidth * safeFitScale * zoom.value));
  const imageHeight = Math.max(1, Math.round(naturalHeight * safeFitScale * zoom.value));

  return {
    imageWidth,
    imageHeight,
    frameWidth: rotatedSideways.value ? imageHeight : imageWidth,
    frameHeight: rotatedSideways.value ? imageWidth : imageHeight,
  };
});
const imageStyle = computed(() => ({
  width: `${fittedImageSize.value.imageWidth}px`,
  height: `${fittedImageSize.value.imageHeight}px`,
}));
const imageRotatorStyle = computed(() => ({
  width: `${fittedImageSize.value.imageWidth}px`,
  height: `${fittedImageSize.value.imageHeight}px`,
  transform: `rotate(${rotation.value}deg)`,
}));
const imageFrameStyle = computed(() => ({
  width: `${Math.max(stageSize.value.width, fittedImageSize.value.frameWidth)}px`,
  height: `${Math.max(stageSize.value.height, fittedImageSize.value.frameHeight)}px`,
}));
let stageResizeObserver: ResizeObserver | null = null;
let slideshowTimer: ReturnType<typeof window.setInterval> | null = null;
const slideshowIntervalMs = 3000;

watch(
  () => props.index,
  () => {
    resetZoom();
    resetRotation();
    resetMediaState();
    cancelTagEdit();
    cancelDescriptionEdit();
    nextTick(() => {
      updateStageSize();
      scrollActiveThumbnailIntoView();
      updateFilmstripScroll();
    });
  },
);

watch(isVideo, (value) => {
  if (value) stopSlideshow();
});

watch(hasMultipleAssets, (value) => {
  if (!value) stopSlideshow();
});

watch(showInfo, () => {
  nextTick(() => {
    updateStageSize();
    centerStageScroll();
  });
});

watch(zoom, () => {
  nextTick(centerStageScroll);
});

watch(filmstripExpanded, (expanded) => {
  if (!expanded) {
    filmstripScrollLeft.value = 0;
    filmstripScrollMax.value = 0;
    return;
  }
  nextTick(() => {
    updateFilmstripScroll();
    scrollActiveThumbnailIntoView();
  });
});

watch(
  () => current.value.tags?.join("\n") ?? "",
  () => {
    if (!tagEditing.value) tagInput.value = currentTags.value.join(', ');
  },
);

watch(
  () => current.value.description ?? '',
  () => {
    if (!descriptionEditing.value) descriptionInput.value = currentDescription.value;
  },
);

onMounted(() => {
  nextTick(() => {
    viewerRef.value?.focus();
    updateStageSize();
    if (stageRef.value && typeof ResizeObserver !== 'undefined') {
      stageResizeObserver = new ResizeObserver(updateStageSize);
      stageResizeObserver.observe(stageRef.value);
    }
  });
  window.addEventListener('keydown', handleKey);
  window.addEventListener('resize', handleWindowResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKey);
  window.removeEventListener('resize', handleWindowResize);
  stageResizeObserver?.disconnect();
  stopSlideshow();
});

function handleWindowResize() {
  updateStageSize();
  updateFilmstripScroll();
}

function handleTouchStart(event: TouchEvent) {
  touchActive.value = false;
  if (!hasMultipleAssets.value) return;
  if (event.touches.length !== 1) return;
  if (!isVideo.value && zoom.value > 1) return;
  const touch = event.touches[0];
  touchStartX.value = touch.clientX;
  touchStartY.value = touch.clientY;
  touchActive.value = true;
}

function handleTouchEnd(event: TouchEvent) {
  if (!touchActive.value || !hasMultipleAssets.value) return;
  touchActive.value = false;
  if (!isVideo.value && zoom.value > 1) return;
  const touch = event.changedTouches[0];
  const deltaX = touch.clientX - touchStartX.value;
  const deltaY = touch.clientY - touchStartY.value;
  if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > minSwipeDistance) {
    event.preventDefault();
    if (deltaX > 0) previous();
    else next();
  }
}

function cancelTouch() {
  touchActive.value = false;
}

function handleKey(event: KeyboardEvent) {
  if (props.shortcutsDisabled) return;
  if (isShortcutSuppressedTarget(event.target)) return;
  if (event.key === 'Escape') {
    emit('close');
    return;
  }
  if (event.key === 'ArrowLeft') previous();
  if (event.key === 'ArrowRight') next();
  if (!isVideo.value && (event.key === '+' || event.key === '=')) zoomIn();
  if (!isVideo.value && event.key === '-') zoomOut();
  if (!isVideo.value && event.key === '0') resetZoom();
  if (!isVideo.value && event.key === '[') rotateLeft();
  if (!isVideo.value && event.key === ']') rotateRight();
  if (event.key === ' ' && !isMediaControlTarget(event.target)) {
    event.preventDefault();
    toggleSlideshow();
  }
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

function toggleFilmstrip() {
  filmstripExpanded.value = !filmstripExpanded.value;
}

function handleFilmstripItemClick(index: number, event: MouseEvent) {
  if (filmstripSuppressClick.value || filmstripDragMoved.value) {
    event.preventDefault();
    return;
  }
  goTo(index);
}

function handleFilmstripPointerDown(event: PointerEvent) {
  if (event.button !== 0) return;
  const container = filmstripRef.value;
  if (!container) return;
  filmstripDragging.value = true;
  filmstripDragMoved.value = false;
  filmstripPointerDownIndex.value = getFilmstripTargetIndex(event.target);
  filmstripDragStartX.value = event.clientX;
  filmstripDragStartScrollLeft.value = container.scrollLeft;
  container.setPointerCapture(event.pointerId);
}

function handleFilmstripPointerMove(event: PointerEvent) {
  if (!filmstripDragging.value) return;
  const container = filmstripRef.value;
  if (!container) return;
  const deltaX = event.clientX - filmstripDragStartX.value;
  if (Math.abs(deltaX) > 4) filmstripDragMoved.value = true;
  container.scrollLeft = filmstripDragStartScrollLeft.value - deltaX;
  updateFilmstripScroll();
}

function endFilmstripDrag(event: PointerEvent) {
  const container = filmstripRef.value;
  if (container?.hasPointerCapture(event.pointerId)) {
    container.releasePointerCapture(event.pointerId);
  }
  const targetIndex = filmstripPointerDownIndex.value;
  const shouldSelect = !filmstripDragMoved.value && targetIndex !== null;
  filmstripDragging.value = false;
  filmstripPointerDownIndex.value = null;
  if (shouldSelect) {
    filmstripSuppressClick.value = true;
    goTo(targetIndex);
    window.setTimeout(() => {
      filmstripSuppressClick.value = false;
    }, 0);
  }
  if (filmstripDragMoved.value) {
    window.setTimeout(() => {
      filmstripDragMoved.value = false;
    }, 0);
  }
}

function updateFilmstripScroll() {
  const container = filmstripRef.value;
  if (!container) {
    filmstripScrollLeft.value = 0;
    filmstripScrollMax.value = 0;
    return;
  }
  filmstripScrollMax.value = Math.max(0, container.scrollWidth - container.clientWidth);
  filmstripScrollLeft.value = Math.min(filmstripScrollMax.value, Math.max(0, container.scrollLeft));
}

function handleFilmstripScrollbarInput(event: Event) {
  const target = event.target;
  const container = filmstripRef.value;
  if (!(target instanceof HTMLInputElement) || !container) return;
  container.scrollLeft = Number(target.value);
  updateFilmstripScroll();
}

function getFilmstripTargetIndex(target: EventTarget | null) {
  if (!(target instanceof Element)) return null;
  const item = target.closest<HTMLElement>('.filmstrip-item');
  const rawIndex = item?.dataset.filmstripIndex;
  if (rawIndex === undefined) return null;
  const index = Number(rawIndex);
  return Number.isInteger(index) && index >= 0 && index < props.assets.length ? index : null;
}

function toggleSlideshow() {
  if (slideshowPlaying.value) {
    stopSlideshow();
  } else {
    startSlideshow();
  }
}

function startSlideshow() {
  if (!hasMultipleAssets.value || isVideo.value) return;
  stopSlideshow();
  slideshowPlaying.value = true;
  slideshowTimer = window.setInterval(() => {
    if (isVideo.value) {
      stopSlideshow();
      return;
    }
    next();
  }, slideshowIntervalMs);
}

function stopSlideshow() {
  if (slideshowTimer) {
    window.clearInterval(slideshowTimer);
    slideshowTimer = null;
  }
  slideshowPlaying.value = false;
}

function isMediaControlTarget(target: EventTarget | null) {
  return target instanceof HTMLVideoElement || target instanceof HTMLButtonElement || target instanceof HTMLAnchorElement;
}

function isShortcutSuppressedTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement ||
    target.isContentEditable
  );
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

function resetRotation() {
  rotation.value = 0;
}

function rotateLeft() {
  rotation.value = normalizeRotation(rotation.value - 90);
  nextTick(centerStageScroll);
}

function rotateRight() {
  rotation.value = normalizeRotation(rotation.value + 90);
  nextTick(centerStageScroll);
}

function normalizeRotation(value: number) {
  return ((value % 360) + 360) % 360;
}

function resetMediaState() {
  mediaLoading.value = true;
  mediaError.value = '';
  imageNaturalSize.value = assetImageSize(current.value);
}

function handleWheel(event: WheelEvent) {
  if (isVideo.value || mediaLoading.value || mediaError.value) return;
  if (event.deltaY < 0) zoomIn();
  if (event.deltaY > 0) zoomOut();
}

function handleImageLoad(event: Event) {
  const image = event.target as HTMLImageElement;
  imageNaturalSize.value = {
    width: image.naturalWidth || current.value.width || 1,
    height: image.naturalHeight || current.value.height || 1,
  };
  mediaLoading.value = false;
  mediaError.value = '';
  nextTick(centerStageScroll);
}

function handleVideoLoad() {
  mediaLoading.value = false;
  mediaError.value = '';
}

function handleMediaError() {
  mediaLoading.value = false;
  mediaError.value = isVideo.value ? t('viewer.videoDisplayFailed') : t('viewer.originalDisplayFailed');
}

function retryMedia() {
  resetZoom();
  resetRotation();
  resetMediaState();
  mediaRetry.value += 1;
}

function beginTagEdit() {
  if (!canEditTags.value) return;
  tagInput.value = currentTags.value.join(', ');
  tagEditing.value = true;
  nextTick(() => {
    tagInputRef.value?.focus();
    tagInputRef.value?.select();
  });
}

function cancelTagEdit() {
  tagEditing.value = false;
  tagInput.value = currentTags.value.join(', ');
}

function saveTags() {
  if (!canEditTags.value) return;
  const tags = normalizeTags(tagInput.value);
  tagEditing.value = false;
  emit('update-tags', current.value, tags);
}

function setRating(value: number) {
  if (!canEditMetadata.value) return;
  emit('update-metadata', current.value, {
    description: currentDescription.value,
    rating: normalizeRating(value),
  });
}

function beginDescriptionEdit() {
  if (!canEditMetadata.value) return;
  descriptionInput.value = currentDescription.value;
  descriptionEditing.value = true;
  nextTick(() => {
    descriptionInputRef.value?.focus();
    descriptionInputRef.value?.select();
  });
}

function cancelDescriptionEdit() {
  descriptionEditing.value = false;
  descriptionInput.value = currentDescription.value;
}

function saveDescription() {
  if (!canEditMetadata.value) return;
  descriptionEditing.value = false;
  emit('update-metadata', current.value, {
    description: descriptionInput.value,
    rating: currentRating.value,
  });
}

function normalizeRating(value: number | null | undefined) {
  if (!Number.isFinite(value)) return 0;
  return Math.min(5, Math.max(0, Math.trunc(value ?? 0)));
}

async function downloadCurrent() {
  if (downloading.value || mediaLoading.value || mediaError.value) return;
  downloading.value = true;
  try {
    const blob = await downloadUrl(assetOriginalUrl(current.value));
    triggerBrowserDownload(blob, current.value.filename);
    emit('downloaded', current.value);
  } catch (err) {
    emit('downloadError', err instanceof Error ? err.message : t('viewer.unableDownloadOriginal'));
  } finally {
    downloading.value = false;
  }
}

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename || 'download';
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
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

function assetImageSize(asset: Asset) {
  return {
    width: Math.max(1, asset.width ?? 1),
    height: Math.max(1, asset.height ?? 1),
  };
}

function assetSourceLabel(asset: Asset) {
  const libraryName = asset.library_name?.trim();
  const folderPath = asset.folder_path?.trim();
  const folderName = asset.folder_name?.trim();
  const parts = [libraryName, folderPath || (folderName && folderName !== libraryName ? folderName : '')].filter(Boolean);
  return parts.join(' / ');
}

function assetCoordinateLabel(asset: Asset) {
  if (typeof asset.latitude !== 'number' || typeof asset.longitude !== 'number') return '';
  return `${asset.latitude.toFixed(5)}, ${asset.longitude.toFixed(5)}`;
}

function updateStageSize() {
  const stage = stageRef.value;
  if (!stage) return;
  const styles = window.getComputedStyle(stage);
  const horizontalPadding = parseCssPixels(styles.paddingLeft) + parseCssPixels(styles.paddingRight);
  const verticalPadding = parseCssPixels(styles.paddingTop) + parseCssPixels(styles.paddingBottom);
  stageSize.value = {
    width: Math.max(1, stage.clientWidth - horizontalPadding),
    height: Math.max(1, stage.clientHeight - verticalPadding),
  };
}

function centerStageScroll() {
  const stage = stageRef.value;
  if (!stage) return;
  stage.scrollTo({
    left: Math.max(0, (stage.scrollWidth - stage.clientWidth) / 2),
    top: Math.max(0, (stage.scrollHeight - stage.clientHeight) / 2),
  });
}

function parseCssPixels(value: string) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeTags(value: string) {
  const seen = new Set<string>();
  const tags: string[] = [];
  for (const rawTag of value.split(/[,，\n]/)) {
    const tag = rawTag.trim().replace(/\s+/g, ' ').slice(0, 40);
    const key = tag.toLocaleLowerCase();
    if (!tag || seen.has(key)) continue;
    tags.push(tag);
    seen.add(key);
    if (tags.length >= 30) break;
  }
  return tags;
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
</script>
