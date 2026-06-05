<template>
  <div class="modal-backdrop">
    <section class="directory-modal">
      <header class="modal-header">
        <div>
          <p class="eyebrow">{{ t('directory.eyebrow') }}</p>
          <h2>{{ t('directory.title') }}</h2>
          <span class="modal-subtitle">{{ platformHint }}</span>
        </div>
        <button class="icon-button" :title="t('common.close')" @click="$emit('close')">
          <X :size="18" />
        </button>
      </header>

      <div class="directory-layout">
        <aside class="root-list">
          <div class="root-list-header">
            <p class="root-list-title">{{ t('directory.recommended') }}</p>
            <small>{{ formatCount(recommendedRoots.length, 'source') }}</small>
          </div>
          <button
            v-for="root in recommendedRoots"
            :key="root.path"
            class="root-button"
            :class="{ active: currentPath === root.path }"
            :title="root.path"
            @click="openPath(root.path)"
          >
            <component :is="rootIcon(root)" :size="17" />
            <span>
              <strong>{{ root.name }}</strong>
              <small>{{ rootSummary(root) }}</small>
            </span>
          </button>
          <div v-if="!recommendedRoots.length" class="root-empty">
            {{ t('directory.noCommonFolders') }}
          </div>
          <button v-if="advancedRoots.length" class="root-disclosure" type="button" @click="showAdvanced = !showAdvanced">
            <ChevronDown v-if="showAdvanced" :size="16" />
            <ChevronRight v-else :size="16" />
            <span>{{ t('directory.advancedLocations') }}</span>
            <small>{{ advancedRoots.length }}</small>
          </button>
          <div v-if="showAdvanced" class="root-group">
            <button
              v-for="root in advancedRoots"
              :key="root.path"
              class="root-button"
              :class="{ active: currentPath === root.path }"
              :title="root.path"
              @click="openPath(root.path)"
            >
              <component :is="rootIcon(root)" :size="17" />
              <span>
                <strong>{{ root.name }}</strong>
                <small>{{ rootSummary(root) }}</small>
              </span>
            </button>
          </div>
        </aside>

        <section class="directory-pane">
          <nav class="path-bar">
            <button v-if="parentPath" class="secondary-button" @click="openPath(parentPath)">
              <ArrowUp :size="16" />
              {{ t('directory.up') }}
            </button>
            <div class="path-stack">
              <div v-if="pathSegments.length" class="path-breadcrumbs">
                <button v-for="segment in pathSegments" :key="segment.path" type="button" @click="openPath(segment.path)">
                  {{ segment.label }}
                </button>
              </div>
              <span v-else>{{ currentPath || t('directory.chooseStartLocation') }}</span>
              <small>{{ directoryHint }}</small>
            </div>
            <button class="primary-button current-folder-action" :disabled="!currentPath || loading || !!error" @click="choose(currentPath)">
              <Check :size="16" />
              {{ t('directory.selectCurrent') }}
            </button>
          </nav>

          <div class="directory-filter">
            <label class="search-box">
              <Search :size="17" />
              <input v-model="filterText" :disabled="loading || !!error" :placeholder="t('directory.filterPlaceholder')" />
              <button v-if="filterText" class="search-clear" type="button" :title="t('common.clearFilter')" @click="filterText = ''">
                <X :size="15" />
              </button>
            </label>
            <small>{{ t('directory.folderResultCount', { shown: visibleEntries.length, total: entries.length }) }}</small>
          </div>

          <div v-if="currentPath && !loading && !error" class="current-folder-summary">
            <FolderOpen :size="17" />
            <span>
              <strong>{{ currentFolderLabel }}</strong>
              <small>{{ currentSummary }} - {{ currentPath }}</small>
            </span>
            <button class="primary-button" @click="choose(currentPath)">
              <Check :size="16" />
              {{ t('directory.useThisFolder') }}
            </button>
          </div>

          <div v-if="loading" class="directory-list directory-loading" :aria-label="t('directory.loadingFolders')">
            <span v-for="item in 7" :key="item" class="directory-skeleton-row"></span>
          </div>
          <div v-else-if="error" class="directory-empty">
            <FolderX :size="26" />
            {{ error }}
          </div>
          <div v-else-if="!entries.length && currentPath" class="directory-empty">
            <FolderOpen :size="26" />
            <strong>{{ t('directory.noSubfolders') }}</strong>
            <span>{{ currentEmptyText }}</span>
            <button class="primary-button" @click="choose(currentPath)">
              <Check :size="17" />
              {{ t('directory.useCurrentFolder') }}
            </button>
          </div>
          <div v-else-if="filterText && !visibleEntries.length" class="directory-empty">
            <Search :size="26" />
            <strong>{{ t('directory.noMatchingFolders') }}</strong>
            <span>{{ t('directory.noFolderMatches', { query: filterText.trim() }) }}</span>
            <button class="secondary-button" @click="filterText = ''">
              <X :size="17" />
              {{ t('common.clearFilter') }}
            </button>
          </div>
          <div v-else-if="!currentPath" class="directory-empty">
            <FolderSearch :size="26" />
            <strong>{{ t('directory.chooseStartLocation') }}</strong>
            <span>{{ t('directory.chooseStartHint') }}</span>
          </div>
          <div v-else class="directory-list">
            <div class="directory-row current-directory-row">
              <button class="directory-main" @click="choose(currentPath)">
                <FolderOpen :size="18" />
                <span>
                  <strong>{{ t('directory.currentFolder') }}</strong>
                  <small>{{ currentSummary }}</small>
                </span>
                <small>{{ currentPath }}</small>
              </button>
              <button class="directory-select primary-select" :title="t('directory.useCurrentFolderTitle')" @click="choose(currentPath)">
                <Check :size="17" />
              </button>
            </div>
            <div v-for="entry in visibleEntries" :key="entry.path" class="directory-row" :class="{ disabled: !entry.is_accessible }">
              <button class="directory-main" :disabled="!entry.is_accessible" @click="openPath(entry.path)">
                <Folder :size="18" />
                <span>
                  <strong>{{ entry.name }}</strong>
                  <small>{{ entrySummary(entry) }}</small>
                </span>
                <small>{{ entry.is_accessible ? entry.path : entry.error }}</small>
              </button>
              <button
                class="directory-select"
                :disabled="!entry.is_accessible"
                :title="t('directory.useThisFolderTitle')"
                @click="choose(entry.path)"
              >
                <Check :size="17" />
              </button>
            </div>
          </div>
        </section>
      </div>

      <footer class="modal-actions directory-actions">
        <label class="manual-path">
          <span>{{ t('directory.manualPath') }}</span>
          <input v-model="manualPath" placeholder="C:\\Photos or /photos/travel" />
        </label>
        <button class="secondary-button" @click="$emit('close')">{{ t('common.cancel') }}</button>
        <button class="primary-button" :disabled="!manualPath" @click="choose(manualPath)">
          <Check :size="17" />
          {{ t('directory.usePath') }}
        </button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  ArrowUp,
  Check,
  ChevronDown,
  ChevronRight,
  Folder,
  FolderHeart,
  FolderOpen,
  FolderSearch,
  FolderX,
  HardDrive,
  Search,
  X,
} from 'lucide-vue-next';
import { useLocale } from '../composables/useLocale';
import { api } from '../services/api';
import type { FilesystemEntry } from '../types';

const emit = defineEmits<{
  close: [];
  select: [path: string];
}>();

const roots = ref<FilesystemEntry[]>([]);
const entries = ref<FilesystemEntry[]>([]);
const currentPath = ref('');
const parentPath = ref<string | null>(null);
const manualPath = ref('');
const filterText = ref('');
const loading = ref(false);
const error = ref('');
const platform = ref('');
const showAdvanced = ref(false);
const currentFolderCount = ref(0);
const currentMediaCount = ref(0);
const { t, formatCount } = useLocale();
const unknownCount = -1;
let previousBodyOverflow = '';
let isBodyScrollLocked = false;

const advancedGroups = new Set(['Advanced', 'Drives', 'Mount points', 'System']);
const recommendedRoots = computed(() => roots.value.filter((root) => !isAdvancedRoot(root)));
const advancedRoots = computed(() => roots.value.filter((root) => isAdvancedRoot(root)));
const visibleEntries = computed(() => {
  const query = filterText.value.trim().toLowerCase();
  if (!query) return entries.value;
  return entries.value.filter((entry) => `${entry.name} ${entry.path}`.toLowerCase().includes(query));
});

const platformHint = computed(() => {
  if (platform.value === 'windows') return t('directory.platformWindows');
  if (recommendedRoots.value.some((root) => root.path === '/photos')) {
    return t('directory.platformDocker');
  }
  if (platform.value) return t('directory.platformLinux');
  return t('directory.platformGeneric');
});
const directoryHint = computed(() => {
  if (!currentPath.value) return t('directory.hintChooseSource');
  if (loading.value) return t('directory.hintLoading');
  if (filterText.value) return t('directory.hintFiltering');
  return t('directory.hintFoldersOnly');
});
const currentSummary = computed(() => formatCounts(currentFolderCount.value, currentMediaCount.value));
const currentFolderLabel = computed(() => {
  if (!currentPath.value) return t('directory.currentFolder');
  const segments = buildPathSegments(currentPath.value);
  return segments[segments.length - 1]?.label ?? currentPath.value;
});
const currentEmptyText = computed(() => {
  if (currentMediaCount.value > 0) return t('directory.emptyWithMedia', { media: formatCount(currentMediaCount.value, 'media') });
  return t('directory.emptyWithoutMedia');
});
const pathSegments = computed(() => buildPathSegments(currentPath.value));

onMounted(async () => {
  lockBodyScroll();
  try {
    const result = await api.filesystemRoots();
    platform.value = result.platform;
    roots.value = result.roots;
    const firstRecommended = recommendedRoots.value[0] ?? result.roots[0];
    if (recommendedRoots.value.length && firstRecommended) {
      await openPath(firstRecommended.path);
    } else if (!result.roots.length) {
      error.value = t('directory.noRoots');
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('directory.unableLoadRoots');
  }
});

onBeforeUnmount(() => {
  unlockBodyScroll();
});

async function openPath(path: string) {
  loading.value = true;
  error.value = '';
  currentPath.value = path;
  manualPath.value = path;
  filterText.value = '';
  try {
    const result = await api.filesystemChildren(path);
    entries.value = result.entries;
    parentPath.value = result.parent_path;
    currentPath.value = result.path;
    manualPath.value = result.path;
    currentFolderCount.value = result.child_folder_count;
    currentMediaCount.value = mediaCount(result);
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('directory.unableLoadFolder');
    entries.value = [];
    currentFolderCount.value = 0;
    currentMediaCount.value = 0;
  } finally {
    loading.value = false;
  }
}

function choose(path: string) {
  const value = path.trim();
  if (!value) return;
  emit('select', value);
}

function isAdvancedRoot(root: FilesystemEntry) {
  return root.kind === 'drive' || advancedGroups.has(root.group ?? '');
}

function rootIcon(root: FilesystemEntry) {
  return root.kind === 'drive' ? HardDrive : FolderHeart;
}

function rootSummary(root: FilesystemEntry) {
  const counts = formatCounts(root.child_folder_count, mediaCount(root));
  return counts ? `${groupLabel(root.group)} - ${counts}` : groupLabel(root.group);
}

function entrySummary(entry: FilesystemEntry) {
  if (!entry.is_accessible) return entry.error || t('directory.notAccessible');
  return formatCounts(entry.child_folder_count, mediaCount(entry));
}

function formatCounts(folderCount: number, mediaCountValue: number) {
  if (folderCount === unknownCount || mediaCountValue === unknownCount) return '';
  return `${formatCount(folderCount, 'folder')} / ${formatCount(mediaCountValue, 'media')}`;
}

function mediaCount(entry: { media_count?: number; image_count: number }) {
  return entry.media_count ?? entry.image_count;
}

function groupLabel(group: string | null) {
  if (group === 'Recommended') return t('directory.groupRecommended');
  if (group === 'Advanced') return t('directory.groupAdvanced');
  if (group === 'Drives') return t('directory.groupDrives');
  if (group === 'Mount points') return t('directory.groupMountPoints');
  if (group === 'System') return t('directory.groupSystem');
  return group || t('directory.location');
}

function buildPathSegments(path: string) {
  if (!path) return [];
  const normalized = path.replace(/\\/g, '/');
  const isWindowsDrive = /^[A-Za-z]:\//.test(normalized);
  if (isWindowsDrive) {
    const drive = normalized.slice(0, 2);
    const rest = normalized.slice(3).split('/').filter(Boolean);
    const segments = [{ label: `${drive}\\`, path: `${drive}\\` }];
    let current = `${drive}\\`;
    for (const part of rest) {
      current = current.endsWith('\\') ? `${current}${part}` : `${current}\\${part}`;
      segments.push({ label: part, path: current });
    }
    return segments;
  }
  const parts = normalized.split('/').filter(Boolean);
  const segments = [{ label: '/', path: '/' }];
  let current = '';
  for (const part of parts) {
    current = `${current}/${part}`;
    segments.push({ label: part, path: current });
  }
  return segments;
}

function lockBodyScroll() {
  if (isBodyScrollLocked || typeof document === 'undefined') return;
  previousBodyOverflow = document.body.style.overflow;
  document.body.style.overflow = 'hidden';
  isBodyScrollLocked = true;
}

function unlockBodyScroll() {
  if (!isBodyScrollLocked || typeof document === 'undefined') return;
  document.body.style.overflow = previousBodyOverflow;
  isBodyScrollLocked = false;
}
</script>
