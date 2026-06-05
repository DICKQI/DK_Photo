<template>
  <main class="share-shell">
    <header class="share-header share-hero">
      <div>
        <p class="eyebrow">{{ t('share.eyebrow') }}</p>
        <h1>{{ share?.title || t('share.sharedPhotos') }}</h1>
        <p class="muted">{{ shareSubtitle }}</p>
      </div>
      <div v-if="!needsPassword" class="share-header-actions">
        <LanguageToggle />
        <button class="secondary-button" @click="copyShareLink">
          <Link2 :size="16" />
          {{ t('album.shareCopyLink') }}
        </button>
        <span class="share-expiry">
          <Images :size="16" />
          {{ formatCount(assets.length, 'media') }}
        </span>
        <span v-if="share?.expires_at" class="share-expiry">
          <Clock :size="16" />
          {{ t('share.expires', { date: formatDate(share.expires_at) }) }}
        </span>
      </div>
    </header>

    <section v-if="needsPassword" class="share-password-section">
      <div class="share-password-card">
        <Lock :size="32" />
        <strong>{{ t('share.passwordRequired') }}</strong>
        <span>{{ t('share.passwordHint') }}</span>
        <form class="share-password-form" @submit.prevent="verifyPassword">
          <input
            v-model="passwordInput"
            type="password"
            class="rename-input"
            :placeholder="t('share.passwordPlaceholder')"
            autofocus
          />
          <p v-if="passwordError" class="share-password-error">{{ passwordError }}</p>
          <button class="primary-button" :disabled="!passwordInput.trim() || verifyingPassword" type="submit">
            <LoaderCircle v-if="verifyingPassword" class="spin" :size="16" />
            {{ verifyingPassword ? t('share.verifying') : t('share.unlock') }}
          </button>
        </form>
      </div>
    </section>

    <section v-if="loading" class="empty-state">
      <div class="skeleton-grid" :aria-label="t('share.loadingSharedPhotos')">
        <span v-for="item in 8" :key="item" class="skeleton-card"></span>
      </div>
    </section>
    <section v-else-if="error" class="empty-state">
      <ImageOff :size="34" />
      <strong>{{ error }}</strong>
    </section>
    <section v-else-if="!assets.length" class="empty-state">
      <ImageOff :size="34" />
      <strong>{{ t('share.noSharedPhotos') }}</strong>
      <span>{{ t('share.noSharedPhotosHint') }}</span>
    </section>
    <template v-else>
      <section class="share-toolbar">
        <div>
          <strong>{{ share?.title || t('share.sharedPhotos') }}</strong>
          <span>{{ t('share.downloadableOriginals', { originals: formatCount(assets.length, 'original') }) }}</span>
        </div>
        <div class="share-toolbar-actions">
          <button class="secondary-button" :disabled="downloadingAll" @click="downloadAllOriginals">
            <LoaderCircle v-if="downloadingAll" class="spin" :size="16" />
            <Download v-else :size="16" />
            {{ downloadingAll ? t('share.downloadingAll') : t('share.downloadAll') }}
          </button>
          <div class="segmented-control" :aria-label="t('album.mediaFilter')">
            <button :class="{ active: mediaFilter === 'all' }" :title="t('album.showAllMedia')" @click="mediaFilter = 'all'">
              <Images :size="16" />
              {{ t('common.all') }}
            </button>
            <button :class="{ active: mediaFilter === 'image' }" :title="t('album.showImagesOnly')" @click="mediaFilter = 'image'">
              <Images :size="16" />
              {{ t('common.photos') }}
            </button>
            <button :class="{ active: mediaFilter === 'video' }" :title="t('album.showVideosOnly')" @click="mediaFilter = 'video'">
              <Play :size="16" />
              {{ t('common.videos') }}
            </button>
          </div>
          <div class="segmented-control sort-control" :aria-label="t('share.sortSharedPhotos')">
            <button :class="{ active: sortMode === 'date' }" :title="t('album.sortByDate')" @click="sortMode = 'date'">
              <Clock :size="16" />
              {{ t('common.sortDate') }}
            </button>
            <button :class="{ active: sortMode === 'name' }" :title="t('album.sortByName')" @click="sortMode = 'name'">
              <ArrowDownAZ :size="16" />
              {{ t('common.sortName') }}
            </button>
            <button :class="{ active: sortDirection === 'asc' }" :title="sortDirectionTitle" @click="toggleSortDirection">
              <ArrowUpAZ v-if="sortDirection === 'asc'" :size="16" />
              <ArrowDownAZ v-else :size="16" />
              {{ sortDirection === 'asc' ? t('common.sortAsc') : t('common.sortDesc') }}
            </button>
          </div>
          <div class="segmented-control" :aria-label="t('share.thumbnailSize')">
            <button :class="{ active: tileMode === 'comfortable' }" :title="t('share.comfortableThumbnails')" @click="tileMode = 'comfortable'">
              <LayoutGrid :size="16" />
              {{ t('common.grid') }}
            </button>
            <button :class="{ active: tileMode === 'large' }" :title="t('share.largeThumbnails')" @click="tileMode = 'large'">
              <Maximize2 :size="16" />
              {{ t('common.large') }}
            </button>
          </div>
        </div>
      </section>

      <section v-if="!displayAssets.length" class="empty-state share-filter-empty">
        <ImageOff :size="34" />
        <strong>{{ t('share.noFilteredMedia') }}</strong>
        <span>{{ t('share.noFilteredMediaHint') }}</span>
        <button class="secondary-button" @click="mediaFilter = 'all'">
          {{ t('common.clearFilter') }}
        </button>
      </section>

      <section v-else class="public-grid" :style="{ '--tile-size': tileSize }">
        <article
          v-for="(asset, index) in displayAssets"
          :key="asset.id"
          class="photo-tile"
          :style="{ '--tile-index': index }"
        >
          <button class="photo-open" @click="openViewer(index)">
            <span class="photo-thumb" :class="{ portrait: isPortraitAsset(asset) }">
              <img :src="publicThumbnailUrl(token, asset.id, shareThumbnailSize)" :alt="asset.filename" loading="lazy" />
              <span v-if="isVideoAsset(asset)" class="photo-media-badge" :title="t('album.videoAsset')">
                <Play :size="14" fill="currentColor" />
              </span>
              <span class="photo-hover">
                <Maximize2 :size="17" />
                {{ t('common.open') }}
              </span>
            </span>
            <span class="photo-name">{{ asset.filename }}</span>
            <span class="photo-meta">
              <span>{{ assetDateLabel(asset) }}</span>
              <span>{{ formatBytes(asset.size) }}</span>
            </span>
          </button>
          <button class="photo-quick-action" :disabled="downloadingAssetId === asset.id" :title="t('common.downloadOriginal')" @click="downloadSingleOriginal(asset)">
            <LoaderCircle v-if="downloadingAssetId === asset.id" class="spin" :size="17" />
            <Download v-else :size="17" />
          </button>
        </article>
      </section>
    </template>

    <PhotoViewer
      v-if="viewerIndex !== null"
      :assets="displayAssets"
      :index="viewerIndex"
      :can-share="false"
      :can-favorite="false"
      :can-locate="false"
      :original-url-for="publicOriginalFor"
      :thumbnail-url-for="publicThumbnailFor"
      @close="viewerIndex = null"
      @update:index="viewerIndex = $event"
      @downloaded="showToast(t('viewer.downloadStarted'))"
      @download-error="showToast($event)"
    />
    <p v-if="toastMessage" class="toast">{{ toastMessage }}</p>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { ArrowDownAZ, ArrowUpAZ, Clock, Download, ImageOff, Images, LayoutGrid, Link2, LoaderCircle, Lock, Maximize2, Play } from 'lucide-vue-next';
import LanguageToggle from '../components/LanguageToggle.vue';
import PhotoViewer from '../components/PhotoViewer.vue';
import { useLocale } from '../composables/useLocale';
import { api, downloadUrl, publicOriginalUrl, publicThumbnailUrl } from '../services/api';
import type { Asset, PublicShare } from '../types';

type ShareSortMode = 'date' | 'name';
type ShareSortDirection = 'asc' | 'desc';
type ShareTileMode = 'comfortable' | 'large';
type ShareMediaFilter = 'all' | 'image' | 'video';

const route = useRoute();
const token = route.params.token as string;
const { t, formatCount, formatDate } = useLocale();
const share = ref<PublicShare | null>(null);
const assets = ref<Asset[]>([]);
const loading = ref(true);
const error = ref('');
const needsPassword = ref(false);
const passwordInput = ref('');
const passwordError = ref('');
const verifyingPassword = ref(false);
const sortMode = ref<ShareSortMode>(storedShareSortMode());
const sortDirection = ref<ShareSortDirection>(storedShareSortDirection());
const tileMode = ref<ShareTileMode>(storedShareTileMode());
const mediaFilter = ref<ShareMediaFilter>(storedShareMediaFilter());
const viewerIndex = ref<number | null>(null);
const downloadingAll = ref(false);
const downloadingAssetId = ref<number | null>(null);
const toastMessage = ref('');
let toastTimer: ReturnType<typeof window.setTimeout> | null = null;

const shareSubtitle = computed(() => {
  if (loading.value) return t('share.preparing');
  if (error.value) return t('share.unopenable');
  return t('share.available', { media: formatCount(assets.value.length, 'media') });
});

const sortedAssets = computed(() => {
  const sorted = [...assets.value];
  if (sortMode.value === 'name') return sorted.sort((a, b) => compareByDirection(a.filename.localeCompare(b.filename)));
  return sorted.sort((a, b) => {
    const left = Date.parse(a.captured_at || a.updated_at) || a.mtime || 0;
    const right = Date.parse(b.captured_at || b.updated_at) || b.mtime || 0;
    return compareByDirection(left - right);
  });
});
const displayAssets = computed(() => {
  if (mediaFilter.value === 'image') return sortedAssets.value.filter((asset) => asset.mime_type.startsWith('image/'));
  if (mediaFilter.value === 'video') return sortedAssets.value.filter((asset) => asset.mime_type.startsWith('video/'));
  return sortedAssets.value;
});

const tileSize = computed(() => (tileMode.value === 'large' ? '260px' : '190px'));
const shareThumbnailSize = computed(() => (tileMode.value === 'large' ? 'large' : 'medium'));
const sortDirectionTitle = computed(() => (sortDirection.value === 'asc' ? t('common.ascendingOrder') : t('common.descendingOrder')));

watch(sortMode, (value) => localStorage.setItem('dk-photo-share-sort-mode', value));
watch(sortDirection, (value) => localStorage.setItem('dk-photo-share-sort-direction', value));
watch(tileMode, (value) => localStorage.setItem('dk-photo-share-tile-mode', value));
watch(mediaFilter, (value) => {
  localStorage.setItem('dk-photo-share-media-filter', value);
  viewerIndex.value = null;
});

onMounted(async () => {
  try {
    share.value = await api.publicShare(token);
    if (share.value.has_password) {
      needsPassword.value = true;
      loading.value = false;
      return;
    }
    assets.value = await api.publicShareAssets(token);
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('share.unavailable');
  } finally {
    loading.value = false;
  }
});

onBeforeUnmount(() => {
  if (toastTimer) window.clearTimeout(toastTimer);
});

function openViewer(index: number) {
  viewerIndex.value = index;
}

async function verifyPassword() {
  if (!passwordInput.value.trim() || verifyingPassword.value) return;
  verifyingPassword.value = true;
  passwordError.value = '';
  try {
    await api.verifySharePassword(token, passwordInput.value);
    needsPassword.value = false;
    loading.value = true;
    assets.value = await api.publicShareAssets(token);
  } catch (err) {
    passwordError.value = err instanceof Error ? err.message : t('share.passwordError');
  } finally {
    verifyingPassword.value = false;
    loading.value = false;
  }
}

async function copyShareLink() {
  try {
    await navigator.clipboard?.writeText(window.location.href);
    showToast(t('admin.shareCopied'));
  } catch {
    showToast(t('admin.unableCopyShare'));
  }
}

function toggleSortDirection() {
  sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc';
  viewerIndex.value = null;
}

function publicOriginalFor(asset: Asset) {
  return publicOriginalUrl(token, asset.id);
}

function publicThumbnailFor(asset: Asset, size: string) {
  return publicThumbnailUrl(token, asset.id, size);
}

function isVideoAsset(asset: Asset) {
  return asset.mime_type.startsWith('video/');
}

function isPortraitAsset(asset: Asset) {
  return !isVideoAsset(asset) && Boolean(asset.width && asset.height && asset.height > asset.width);
}

async function downloadAllOriginals() {
  if (downloadingAll.value) return;
  downloadingAll.value = true;
  try {
    const archive = await api.downloadPublicShare(token);
    triggerBrowserDownload(archive, 'dk-photo-share-originals.zip');
    showToast(t('viewer.downloadStarted'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('share.unableDownloadAll'));
  } finally {
    downloadingAll.value = false;
  }
}

async function downloadSingleOriginal(asset: Asset) {
  if (downloadingAssetId.value !== null) return;
  downloadingAssetId.value = asset.id;
  try {
    const original = await downloadUrl(publicOriginalUrl(token, asset.id));
    triggerBrowserDownload(original, asset.filename);
    showToast(t('viewer.downloadStarted'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('viewer.unableDownloadOriginal'));
  } finally {
    downloadingAssetId.value = null;
  }
}

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function showToast(message: string) {
  toastMessage.value = message;
  if (toastTimer) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toastMessage.value = '';
  }, 3200);
}

function storedShareSortMode(): ShareSortMode {
  const value = localStorage.getItem('dk-photo-share-sort-mode');
  return value === 'date' || value === 'name' ? value : 'date';
}

function storedShareSortDirection(): ShareSortDirection {
  const value = localStorage.getItem('dk-photo-share-sort-direction');
  return value === 'asc' || value === 'desc' ? value : 'desc';
}

function storedShareTileMode(): ShareTileMode {
  const value = localStorage.getItem('dk-photo-share-tile-mode');
  return value === 'comfortable' || value === 'large' ? value : 'comfortable';
}

function storedShareMediaFilter(): ShareMediaFilter {
  const value = localStorage.getItem('dk-photo-share-media-filter');
  return value === 'image' || value === 'video' ? value : 'all';
}

function compareByDirection(value: number) {
  return sortDirection.value === 'asc' ? value : -value;
}

function assetDateLabel(asset: Asset) {
  const raw = asset.captured_at || asset.updated_at;
  return formatDate(raw);
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
</script>
