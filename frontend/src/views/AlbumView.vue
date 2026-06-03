<template>
  <main class="app-shell">
    <aside class="sidebar">
      <div class="brand-row">
          <div class="brand-mark">DK</div>
          <div>
            <strong>DK Photo</strong>
          <span>{{ t('album.folderView') }}</span>
          </div>
        </div>
      <button class="sidebar-action" :class="{ active: !currentFolder }" @click="goRoot">
        <FolderRoot :size="18" />
        {{ t('album.allLibraries') }}
      </button>
      <label class="library-filter">
        <Search :size="16" />
        <input v-model="libraryFilter" :placeholder="t('album.filterLibraries')" />
        <button v-if="libraryFilter" class="search-clear" type="button" :title="t('album.clearLibraryFilter')" @click="libraryFilter = ''">
          <X :size="14" />
        </button>
      </label>
      <div class="sidebar-meta">
        <span>{{ libraryListSummary }}</span>
        <button v-if="libraryFilter" type="button" @click="libraryFilter = ''">{{ t('common.reset') }}</button>
      </div>
      <div class="tree-scroll">
        <button
          v-for="folder in filteredRootFolders"
          :key="folder.id"
          class="tree-item"
          :class="{ active: currentFolder?.id === folder.id }"
          @click="openFolder(folder)"
        >
          <Folder :size="17" />
          <span>{{ folder.name }}</span>
          <small>{{ folder.photo_count }}</small>
        </button>
        <div v-if="rootFolders.length && !filteredRootFolders.length" class="tree-empty">
          <Search :size="18" />
          <span>{{ t('album.noMatchingLibraries') }}</span>
        </div>
      </div>
      <RouterLink v-if="user?.role === 'admin'" class="admin-link" to="/admin">
        <Settings :size="18" />
        {{ t('common.management') }}
      </RouterLink>
    </aside>

    <section class="content-pane">
      <header class="topbar">
        <button class="icon-button mobile-only" @click="mobileTree = !mobileTree" :title="t('album.foldersTitle')">
          <PanelLeft :size="19" />
        </button>
        <nav class="breadcrumbs">
          <button @click="goRoot">{{ t('album.breadcrumbLibraries') }}</button>
          <template v-for="ancestor in currentFolder?.ancestors || []" :key="ancestor.id">
            <ChevronRight :size="15" />
            <button @click="openFolder(ancestor)">{{ ancestor.name }}</button>
          </template>
          <template v-if="currentFolder">
            <ChevronRight :size="15" />
            <span>{{ currentFolder.name }}</span>
          </template>
        </nav>
        <div class="topbar-actions">
          <button
            v-if="currentFolder"
            class="icon-button"
            :class="{ active: selectionMode }"
            :title="selectionMode ? t('album.cancelSelection') : t('album.selectPhotos')"
            @click="toggleSelectionMode"
          >
            <ListChecks :size="18" />
          </button>
          <label class="search-box" :class="{ searching: searchLoading }">
            <LoaderCircle v-if="searchLoading" class="spin" :size="17" />
            <Search v-else :size="17" />
            <input
              v-model="search"
              :disabled="!currentFolder || loading"
              :placeholder="currentFolder ? t('album.searchThisFolder') : t('album.openFolderToSearch')"
              @input="queueAssetSearch"
            />
            <button v-if="search" class="search-clear" type="button" :title="t('common.clearSearch')" @click="clearSearch">
              <X :size="15" />
            </button>
          </label>
          <div class="segmented-control sort-control" :aria-label="t('album.sortPhotos')">
            <button :class="{ active: sortMode === 'date' }" :title="t('album.sortByDate')" @click="setSortMode('date')">
              <Clock :size="16" />
              {{ t('common.sortDate') }}
            </button>
            <button :class="{ active: sortMode === 'name' }" :title="t('album.sortByName')" @click="setSortMode('name')">
              <ArrowDownAZ :size="16" />
              {{ t('common.sortName') }}
            </button>
            <button :class="{ active: sortMode === 'size' }" :title="t('album.sortBySize')" @click="setSortMode('size')">
              <HardDrive :size="16" />
              {{ t('common.sortSize') }}
            </button>
            <button :class="{ active: sortDirection === 'asc' }" :title="sortDirectionTitle" @click="toggleSortDirection">
              <ArrowUpAZ v-if="sortDirection === 'asc'" :size="16" />
              <ArrowDownAZ v-else :size="16" />
              {{ sortDirection === 'asc' ? t('common.sortAsc') : t('common.sortDesc') }}
            </button>
          </div>
          <div class="segmented-control" :aria-label="t('album.thumbnailSize')">
            <button :class="{ active: thumbSize === 'small' }" :title="t('album.compactThumbnails')" @click="setThumbSize('small')">
              <Grid2X2 :size="16" />
              {{ t('common.compact') }}
            </button>
            <button :class="{ active: thumbSize === 'medium' }" :title="t('album.balancedThumbnails')" @click="setThumbSize('medium')">
              <LayoutGrid :size="16" />
              {{ t('common.balanced') }}
            </button>
            <button :class="{ active: thumbSize === 'large' }" :title="t('album.largeThumbnails')" @click="setThumbSize('large')">
              <Maximize2 :size="16" />
              {{ t('common.large') }}
            </button>
          </div>
          <LanguageToggle />
          <button class="icon-button" :title="t('common.toggleTheme')" @click="toggleTheme">
            <Sun v-if="isDark" :size="18" />
            <Moon v-else :size="18" />
          </button>
          <button class="icon-button" :title="t('common.signOut')" @click="logout">
            <LogOut :size="18" />
          </button>
        </div>
      </header>

      <div v-if="mobileTree" class="mobile-folder-sheet">
        <div class="mobile-sheet-header">
          <strong>{{ t('common.libraries') }}</strong>
          <button class="icon-button" :title="t('album.closeFolders')" @click="mobileTree = false">
            <X :size="17" />
          </button>
        </div>
        <label class="library-filter mobile-library-filter">
          <Search :size="16" />
          <input v-model="libraryFilter" :placeholder="t('album.filterLibraries')" />
          <button v-if="libraryFilter" class="search-clear" type="button" :title="t('album.clearLibraryFilter')" @click="libraryFilter = ''">
            <X :size="14" />
          </button>
        </label>
        <button class="mobile-folder-button" :class="{ active: !currentFolder }" @click="goRoot">
          <FolderRoot :size="17" />
          <span>{{ t('album.allLibraries') }}</span>
          <small>{{ rootFolders.length }}</small>
        </button>
        <button
          v-for="folder in filteredRootFolders"
          :key="folder.id"
          class="mobile-folder-button"
          :class="{ active: currentFolder?.id === folder.id }"
          @click="openFolder(folder)"
        >
          <Folder :size="17" />
          <span>{{ folder.name }}</span>
          <small>{{ folder.photo_count }}</small>
        </button>
        <div v-if="!rootFolders.length" class="mobile-sheet-empty">
          {{ t('album.noLibrariesAvailable') }}
        </div>
        <div v-else-if="!filteredRootFolders.length" class="mobile-sheet-empty">
          {{ t('album.noLibrariesMatch', { query: libraryFilter.trim() }) }}
        </div>
      </div>

      <section class="library-status">
        <div>
          <p class="eyebrow">{{ t('album.libraryEyebrow') }}</p>
          <h1>{{ currentFolder?.name || t('album.allLibraries') }}</h1>
        </div>
        <div class="status-metrics">
          <span>
            <Folder :size="16" />
            {{ formatCount(childFolders.length, 'folder') }}
          </span>
          <span>
            <Images :size="16" />
            {{ formatCount(assets.length, 'photo') }}
          </span>
        </div>
      </section>

      <section v-if="loading" class="empty-state">
        <div class="skeleton-grid" :aria-label="t('album.loadingPhotos')">
          <span v-for="item in 8" :key="item" class="skeleton-card"></span>
        </div>
      </section>

      <section v-else-if="error" class="empty-state">
        <ImageOff :size="34" />
        <strong>{{ error }}</strong>
        <button class="secondary-button" @click="retryCurrentView">
          <RefreshCw :size="17" />
          {{ t('common.tryAgain') }}
        </button>
      </section>

      <section v-else-if="!childFolders.length && !assets.length" class="empty-state" :class="{ 'search-empty': hasSearch }">
        <Search v-if="hasSearch" :size="34" />
        <ImageOff v-else :size="34" />
        <strong>{{ hasSearch ? t('album.noMatchesFound') : t('album.noPhotosHere') }}</strong>
        <span v-if="hasSearch">{{ t('album.nothingMatches', { query: searchQuery }) }}</span>
        <span v-else>{{ t('album.emptyHint') }}</span>
        <button v-if="hasSearch" class="secondary-button" @click="clearSearch">
          <X :size="17" />
          {{ t('common.clearSearch') }}
        </button>
      </section>

      <section v-else class="grid-wrap" :style="{ '--tile-size': tileSize }">
        <button
          v-for="(folder, folderIndex) in childFolders"
          :key="folder.id"
          class="folder-card"
          :style="{ '--tile-index': folderIndex }"
          @click="openFolder(folder)"
          @contextmenu.prevent="openContextMenu($event, folder)"
        >
          <div class="folder-cover">
            <img v-if="folder.cover_asset_id" :src="thumbnailUrl(folder.cover_asset_id, 'small')" alt="" loading="lazy" />
            <Folder :size="42" v-else />
          </div>
          <strong>{{ folder.name }}</strong>
          <span>{{ t('album.folderCardMeta', { photos: formatCount(folder.photo_count, 'photo'), folders: formatCount(folder.folder_count, 'folder') }) }}</span>
        </button>

        <article
          v-for="(asset, index) in displayAssets"
          :key="asset.id"
          class="photo-tile"
          :class="{ selected: selectedAssetIds.has(asset.id) }"
          :style="{ '--tile-index': childFolders.length + index }"
        >
          <button v-if="selectionMode" class="photo-select-overlay" @click="toggleAssetSelection(asset.id)">
            <span class="photo-thumb">
              <img :src="thumbnailUrl(asset.id, thumbSize)" :alt="asset.filename" loading="lazy" />
              <span class="photo-select-check" :class="{ checked: selectedAssetIds.has(asset.id) }">
                <Check v-if="selectedAssetIds.has(asset.id)" :size="18" />
              </span>
            </span>
            <span class="photo-name">{{ asset.filename }}</span>
            <span class="photo-meta">
              <span>{{ assetDateLabel(asset) }}</span>
              <span>{{ formatBytes(asset.size) }}</span>
            </span>
          </button>
          <template v-else>
            <button class="photo-open" @click="openViewer(index)">
              <span class="photo-thumb">
                <img :src="thumbnailUrl(asset.id, thumbSize)" :alt="asset.filename" loading="lazy" />
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
            <button class="photo-quick-action" :title="t('album.copyShareLink')" @click="shareAsset(asset)">
              <Share2 :size="17" />
            </button>
          </template>
        </article>
      </section>
    </section>

    <PhotoViewer
      v-if="viewerIndex !== null"
      :assets="displayAssets"
      :index="viewerIndex"
      @close="viewerIndex = null"
      @update:index="viewerIndex = $event"
      @share="shareAsset"
    />
    <p v-if="toastMessage" class="toast">{{ toastMessage }}</p>

    <Teleport to="body">
      <div v-if="selectionMode && selectedAssetIds.size > 0" class="selection-action-bar">
        <span class="selection-count">
          <Check :size="18" />
          {{ selectedCountLabel }}
        </span>
        <div class="selection-actions">
          <button class="secondary-button" @click="clearSelection">
            <X :size="17" />
            {{ t('album.cancelSelection') }}
          </button>
          <button class="primary-button" @click="shareSelectedAssets">
            <Share2 :size="17" />
            {{ t('album.shareSelected') }}
          </button>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="contextMenuFolder"
        class="context-menu-backdrop"
        @click="closeContextMenu"
        @contextmenu.prevent="closeContextMenu"
      />
      <ul
        v-if="contextMenuFolder"
        class="context-menu"
        :style="{ left: contextMenuPos.x + 'px', top: contextMenuPos.y + 'px' }"
      >
        <li>
          <button @click="openCoverPicker(contextMenuFolder!)">
            <Images :size="16" />
            {{ t('album.changeCover') }}
          </button>
        </li>
      </ul>
    </Teleport>

    <Teleport to="body">
      <div v-if="coverPickerFolder" class="modal-backdrop" @click="closeCoverPicker">
        <div class="cover-picker-modal" @click.stop>
          <div class="modal-header">
            <div>
              <strong>{{ t('album.selectCoverPhoto') }}</strong>
              <span class="modal-subtitle">{{ coverPickerFolder.name }}</span>
            </div>
            <button class="icon-button" :title="t('common.close')" @click="closeCoverPicker">
              <X :size="18" />
            </button>
          </div>
          <div v-if="coverPickerLoading" class="cover-picker-loading">
            <LoaderCircle class="spin" :size="28" />
            <span>{{ t('album.loadingPhotos') }}</span>
          </div>
          <div v-else-if="!coverPickerAssets.length" class="cover-picker-empty">
            <ImageOff :size="32" />
            <span>{{ t('album.noPhotosHere') }}</span>
          </div>
          <div v-else class="cover-picker-grid">
            <button
              v-for="asset in coverPickerAssets"
              :key="asset.id"
              class="cover-picker-item"
              :class="{ selected: asset.id === coverPickerFolder.cover_asset_id }"
              @click="selectCover(asset.id)"
            >
              <img :src="thumbnailUrl(asset.id, 'small')" :alt="asset.filename" loading="lazy" />
              <span v-if="asset.id === coverPickerFolder.cover_asset_id" class="current-cover-badge">
                {{ t('album.currentCover') }}
              </span>
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import {
  ArrowDownAZ,
  ArrowUpAZ,
  Check,
  ChevronRight,
  Clock,
  Folder,
  FolderRoot,
  Grid2X2,
  HardDrive,
  ImageOff,
  Images,
  LayoutGrid,
  ListChecks,
  LoaderCircle,
  LogOut,
  Maximize2,
  Moon,
  PanelLeft,
  RefreshCw,
  Search,
  Settings,
  Share2,
  Sun,
  X,
} from 'lucide-vue-next';
import LanguageToggle from '../components/LanguageToggle.vue';
import PhotoViewer from '../components/PhotoViewer.vue';
import { useLocale } from '../composables/useLocale';
import { useTheme } from '../composables/useTheme';
import { api, thumbnailUrl } from '../services/api';
import type { Asset, Folder as FolderType, User } from '../types';

type ThumbSize = 'small' | 'medium' | 'large';
type SortMode = 'date' | 'name' | 'size';
type SortDirection = 'asc' | 'desc';

const router = useRouter();
const { isDark, toggleTheme } = useTheme();
const { t, formatCount, formatDate } = useLocale();
const user = ref<User | null>(null);
const rootFolders = ref<FolderType[]>([]);
const childFolders = ref<FolderType[]>([]);
const currentFolder = ref<FolderType | null>(null);
const assets = ref<Asset[]>([]);
const search = ref('');
const libraryFilter = ref('');
const thumbSize = ref<ThumbSize>(storedThumbSize());
const sortMode = ref<SortMode>(storedSortMode());
const sortDirection = ref<SortDirection>(storedSortDirection());
const loading = ref(true);
const searchLoading = ref(false);
const error = ref('');
const viewerIndex = ref<number | null>(null);
const mobileTree = ref(false);
const toastMessage = ref('');
let toastTimer: ReturnType<typeof setTimeout> | null = null;
let searchTimer: ReturnType<typeof setTimeout> | null = null;
let assetRequestId = 0;

const contextMenuFolder = ref<FolderType | null>(null);
const contextMenuPos = ref({ x: 0, y: 0 });
const coverPickerFolder = ref<FolderType | null>(null);
const coverPickerAssets = ref<Asset[]>([]);
const coverPickerLoading = ref(false);
const selectionMode = ref(false);
const selectedAssetIds = ref(new Set<number>());

const tileSize = computed(() => {
  if (thumbSize.value === 'small') return '150px';
  if (thumbSize.value === 'large') return '260px';
  return '200px';
});

const displayAssets = computed(() => {
  const sorted = [...assets.value];
  if (sortMode.value === 'name') {
    return sorted.sort((a, b) => compareByDirection(a.filename.localeCompare(b.filename)));
  }
  if (sortMode.value === 'size') {
    return sorted.sort((a, b) => compareByDirection(a.size - b.size));
  }
  return sorted.sort((a, b) => {
    const left = Date.parse(a.captured_at || a.updated_at) || a.mtime || 0;
    const right = Date.parse(b.captured_at || b.updated_at) || b.mtime || 0;
    return compareByDirection(left - right);
  });
});
const searchQuery = computed(() => search.value.trim());
const hasSearch = computed(() => searchQuery.value.length > 0);
const sortDirectionTitle = computed(() => (sortDirection.value === 'asc' ? t('common.ascendingOrder') : t('common.descendingOrder')));
const filteredRootFolders = computed(() => {
  const query = libraryFilter.value.trim().toLowerCase();
  if (!query) return rootFolders.value;
  return rootFolders.value.filter((folder) => folder.name.toLowerCase().includes(query));
});
const libraryListSummary = computed(() => {
  if (!rootFolders.value.length) return t('album.noLibrariesAvailable');
  if (!libraryFilter.value.trim()) return formatCount(rootFolders.value.length, 'library');
  return t('admin.shownPartial', { shown: filteredRootFolders.value.length, total: rootFolders.value.length });
});
const selectedCountLabel = computed(() => {
  const count = selectedAssetIds.value.size;
  return t(count === 1 ? 'album.photoSelected' : 'album.photosSelected', { count });
});

watch(thumbSize, (value) => localStorage.setItem('dk-photo-thumb-size', value));
watch(sortMode, (value) => localStorage.setItem('dk-photo-sort-mode', value));
watch(sortDirection, (value) => localStorage.setItem('dk-photo-sort-direction', value));

onUnmounted(() => {
  if (toastTimer) window.clearTimeout(toastTimer);
  cancelSearchTimer();
});

onMounted(async () => {
  try {
    user.value = await api.me();
    await loadRoot();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadApp');
    loading.value = false;
  }
});

async function loadRoot() {
  loading.value = true;
  error.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  assetRequestId += 1;
  currentFolder.value = null;
  viewerIndex.value = null;
  try {
    childFolders.value = await api.folders(null);
    rootFolders.value = childFolders.value;
    assets.value = [];
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadLibraries');
  } finally {
    loading.value = false;
  }
}

async function openFolder(folder: FolderType) {
  loading.value = true;
  error.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  assetRequestId += 1;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  try {
    currentFolder.value = await api.folder(folder.id);
    childFolders.value = await api.folders(folder.id);
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableOpenFolder');
  } finally {
    loading.value = false;
  }
}

function goRoot() {
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  mobileTree.value = false;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  loadRoot();
}

async function loadAssets({ showSearchLoading = false }: { showSearchLoading?: boolean } = {}) {
  if (!currentFolder.value) return;
  const requestId = ++assetRequestId;
  const folderId = currentFolder.value.id;
  const query = searchQuery.value;
  if (showSearchLoading) searchLoading.value = true;
  try {
    const nextAssets = await api.assets(folderId, query);
    if (requestId !== assetRequestId) return;
    assets.value = nextAssets;
    error.value = '';
  } catch (err) {
    if (requestId === assetRequestId) {
      error.value = err instanceof Error ? err.message : t('album.unableLoadPhotos');
    }
  } finally {
    if (requestId === assetRequestId && showSearchLoading) {
      searchLoading.value = false;
    }
  }
}

function queueAssetSearch() {
  if (!currentFolder.value) return;
  cancelSearchTimer();
  searchLoading.value = true;
  searchTimer = window.setTimeout(() => {
    loadAssets({ showSearchLoading: true });
  }, 280);
}

function clearSearch() {
  if (!search.value) return;
  search.value = '';
  cancelSearchTimer();
  if (currentFolder.value) {
    loadAssets({ showSearchLoading: true });
  }
}

function cancelSearchTimer() {
  if (searchTimer) {
    window.clearTimeout(searchTimer);
    searchTimer = null;
  }
}

async function logout() {
  await api.logout();
  await router.push('/login');
}

function openViewer(index: number) {
  viewerIndex.value = index;
}

async function shareAsset(asset: Asset) {
  try {
    const share = await api.createShare({ asset_id: asset.id, title: asset.filename, expires_in_days: 7 });
    await navigator.clipboard?.writeText(`${location.origin}/share/${share.token}`);
    showToast(t('album.shareCopied'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableCreateShare'));
  }
}

function openContextMenu(event: MouseEvent, folder: FolderType) {
  contextMenuFolder.value = folder;
  contextMenuPos.value = { x: event.clientX, y: event.clientY };
}

function closeContextMenu() {
  contextMenuFolder.value = null;
}

async function openCoverPicker(folder: FolderType) {
  closeContextMenu();
  coverPickerFolder.value = folder;
  coverPickerLoading.value = true;
  coverPickerAssets.value = [];
  try {
    coverPickerAssets.value = await api.assets(folder.id, '', true);
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableLoadPhotos'));
    coverPickerFolder.value = null;
  } finally {
    coverPickerLoading.value = false;
  }
}

async function selectCover(assetId: number) {
  if (!coverPickerFolder.value) return;
  const folder = coverPickerFolder.value;
  try {
    const updated = await api.updateFolderCover(folder.id, assetId);
    folder.cover_asset_id = updated.cover_asset_id;
    const idx = childFolders.value.findIndex((f) => f.id === folder.id);
    if (idx !== -1) childFolders.value[idx] = updated;
    showToast(t('album.coverUpdated'));
    coverPickerFolder.value = null;
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateCover'));
  }
}

function closeCoverPicker() {
  coverPickerFolder.value = null;
}

function toggleSelectionMode() {
  selectionMode.value = !selectionMode.value;
  if (!selectionMode.value) {
    selectedAssetIds.value = new Set();
  }
}

function toggleAssetSelection(assetId: number) {
  const next = new Set(selectedAssetIds.value);
  if (next.has(assetId)) {
    next.delete(assetId);
  } else {
    next.add(assetId);
  }
  selectedAssetIds.value = next;
}

function clearSelection() {
  selectedAssetIds.value = new Set();
}

async function shareSelectedAssets() {
  const ids = Array.from(selectedAssetIds.value);
  if (!ids.length) return;
  try {
    const share = await api.createShare({ asset_ids: ids, title: '', expires_in_days: 7 });
    await navigator.clipboard?.writeText(`${location.origin}/share/${share.token}`);
    showToast(t('album.shareCopied'));
    toggleSelectionMode();
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableCreateMultiShare'));
  }
}

function setThumbSize(value: ThumbSize) {
  thumbSize.value = value;
}

function setSortMode(value: SortMode) {
  sortMode.value = value;
  viewerIndex.value = null;
}

function toggleSortDirection() {
  sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc';
  viewerIndex.value = null;
}

function retryCurrentView() {
  if (currentFolder.value) {
    openFolder(currentFolder.value);
  } else {
    loadRoot();
  }
}

function showToast(message: string) {
  toastMessage.value = message;
  if (toastTimer) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toastMessage.value = '';
  }, 3200);
}

function storedThumbSize(): ThumbSize {
  const value = localStorage.getItem('dk-photo-thumb-size');
  return value === 'small' || value === 'medium' || value === 'large' ? value : 'medium';
}

function storedSortMode(): SortMode {
  const value = localStorage.getItem('dk-photo-sort-mode');
  return value === 'date' || value === 'name' || value === 'size' ? value : 'date';
}

function storedSortDirection(): SortDirection {
  const value = localStorage.getItem('dk-photo-sort-direction');
  return value === 'asc' || value === 'desc' ? value : 'desc';
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
