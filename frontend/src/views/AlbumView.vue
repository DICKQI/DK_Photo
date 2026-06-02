<template>
  <main class="app-shell">
    <aside class="sidebar">
      <div class="brand-row">
        <div class="brand-mark">DK</div>
        <div>
          <strong>DK Photo</strong>
          <span>文件夹视图</span>
        </div>
      </div>
      <button class="sidebar-action" @click="goRoot">
        <FolderRoot :size="18" />
        全部图库
      </button>
      <div class="tree-scroll">
        <button
          v-for="folder in rootFolders"
          :key="folder.id"
          class="tree-item"
          :class="{ active: currentFolder?.id === folder.id }"
          @click="openFolder(folder)"
        >
          <Folder :size="17" />
          <span>{{ folder.name }}</span>
          <small>{{ folder.photo_count }}</small>
        </button>
      </div>
      <RouterLink v-if="user?.role === 'admin'" class="admin-link" to="/admin">
        <Settings :size="18" />
        管理
      </RouterLink>
    </aside>

    <section class="content-pane">
      <header class="topbar">
        <button class="icon-button mobile-only" @click="mobileTree = !mobileTree" title="文件夹">
          <PanelLeft :size="19" />
        </button>
        <nav class="breadcrumbs">
          <button @click="goRoot">图库</button>
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
          <label class="search-box">
            <Search :size="17" />
            <input v-model="search" placeholder="搜索当前文件夹" @input="loadAssets" />
          </label>
          <select v-model="thumbSize" class="select-control" title="缩略图尺寸">
            <option value="small">紧凑</option>
            <option value="medium">均衡</option>
            <option value="large">大图</option>
          </select>
          <button class="icon-button" title="退出登录" @click="logout">
            <LogOut :size="18" />
          </button>
        </div>
      </header>

      <div v-if="mobileTree" class="mobile-folder-sheet">
        <button v-for="folder in rootFolders" :key="folder.id" @click="openFolder(folder)">
          <Folder :size="17" />
          {{ folder.name }}
        </button>
      </div>

      <section class="library-status">
        <div>
          <p class="eyebrow">Library</p>
          <h1>{{ currentFolder?.name || '全部图库' }}</h1>
        </div>
        <p class="muted">{{ statusText }}</p>
      </section>

      <section v-if="loading" class="empty-state">
        <LoaderCircle class="spin" :size="28" />
        正在载入照片
      </section>

      <section v-else-if="!childFolders.length && !assets.length" class="empty-state">
        <ImageOff :size="34" />
        <strong>这里还没有照片</strong>
        <span>请在管理页添加图库并扫描，或选择其他文件夹。</span>
      </section>

      <section v-else class="grid-wrap">
        <button v-for="folder in childFolders" :key="folder.id" class="folder-card" @click="openFolder(folder)">
          <div class="folder-cover">
            <img v-if="folder.cover_asset_id" :src="thumbnailUrl(folder.cover_asset_id, 'small')" alt="" loading="lazy" />
            <Folder :size="42" v-else />
          </div>
          <strong>{{ folder.name }}</strong>
          <span>{{ folder.photo_count }} 张照片 · {{ folder.folder_count }} 个文件夹</span>
        </button>

        <button
          v-for="(asset, index) in assets"
          :key="asset.id"
          class="photo-tile"
          :style="{ '--tile-size': tileSize }"
          @click="openViewer(index)"
        >
          <img :src="thumbnailUrl(asset.id, thumbSize)" :alt="asset.filename" loading="lazy" />
          <span>{{ asset.filename }}</span>
        </button>
      </section>
    </section>

    <PhotoViewer
      v-if="viewerIndex !== null"
      :assets="assets"
      :index="viewerIndex"
      @close="viewerIndex = null"
      @update:index="viewerIndex = $event"
      @share="shareAsset"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import {
  ChevronRight,
  Folder,
  FolderRoot,
  ImageOff,
  LoaderCircle,
  LogOut,
  PanelLeft,
  Search,
  Settings,
} from 'lucide-vue-next';
import PhotoViewer from '../components/PhotoViewer.vue';
import { api, thumbnailUrl } from '../services/api';
import type { Asset, Folder as FolderType, User } from '../types';

const router = useRouter();
const user = ref<User | null>(null);
const rootFolders = ref<FolderType[]>([]);
const childFolders = ref<FolderType[]>([]);
const currentFolder = ref<FolderType | null>(null);
const assets = ref<Asset[]>([]);
const search = ref('');
const thumbSize = ref(localStorage.getItem('dk-photo-thumb-size') || 'medium');
const loading = ref(true);
const viewerIndex = ref<number | null>(null);
const mobileTree = ref(false);

const tileSize = computed(() => {
  if (thumbSize.value === 'small') return '150px';
  if (thumbSize.value === 'large') return '260px';
  return '200px';
});

const statusText = computed(() => {
  const photoCount = assets.value.length;
  const folderCount = childFolders.value.length;
  return `${folderCount} 个文件夹 · ${photoCount} 张照片`;
});

watch(thumbSize, (value) => localStorage.setItem('dk-photo-thumb-size', value));

onMounted(async () => {
  user.value = await api.me();
  await loadRoot();
});

async function loadRoot() {
  loading.value = true;
  currentFolder.value = null;
  childFolders.value = await api.folders(null);
  rootFolders.value = childFolders.value;
  assets.value = [];
  loading.value = false;
}

async function openFolder(folder: FolderType) {
  loading.value = true;
  mobileTree.value = false;
  currentFolder.value = await api.folder(folder.id);
  childFolders.value = await api.folders(folder.id);
  await loadAssets();
  loading.value = false;
}

function goRoot() {
  search.value = '';
  loadRoot();
}

async function loadAssets() {
  if (!currentFolder.value) return;
  assets.value = await api.assets(currentFolder.value.id, search.value);
}

async function logout() {
  await api.logout();
  await router.push('/login');
}

function openViewer(index: number) {
  viewerIndex.value = index;
}

async function shareAsset(asset: Asset) {
  const share = await api.createShare({ asset_id: asset.id, title: asset.filename, expires_in_days: 7 });
  await navigator.clipboard?.writeText(`${location.origin}/share/${share.token}`);
  alert('分享链接已复制，有效期 7 天。');
}
</script>
