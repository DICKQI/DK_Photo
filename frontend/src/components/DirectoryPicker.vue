<template>
  <div class="modal-backdrop">
    <section class="directory-modal">
      <header class="modal-header">
        <div>
          <p class="eyebrow">Filesystem</p>
          <h2>Select Library Folder</h2>
        </div>
        <button class="icon-button" title="Close" @click="$emit('close')">
          <X :size="18" />
        </button>
      </header>

      <div class="directory-layout">
        <aside class="root-list">
          <button
            v-for="root in roots"
            :key="root.path"
            class="root-button"
            :class="{ active: currentPath === root.path }"
            @click="openPath(root.path)"
          >
            <HardDrive :size="17" />
            {{ root.name }}
          </button>
        </aside>

        <section class="directory-pane">
          <nav class="path-bar">
            <button v-if="parentPath" class="secondary-button" @click="openPath(parentPath)">
              <ArrowUp :size="16" />
              Up
            </button>
            <span>{{ currentPath || 'Choose a root' }}</span>
          </nav>

          <div v-if="loading" class="directory-empty">
            <LoaderCircle class="spin" :size="24" />
            Loading folders
          </div>
          <div v-else class="directory-list">
            <button
              v-for="entry in entries"
              :key="entry.path"
              class="directory-row"
              :disabled="!entry.is_accessible"
              @click="openPath(entry.path)"
            >
              <Folder :size="18" />
              <span>{{ entry.name }}</span>
              <small>{{ entry.is_accessible ? entry.path : entry.error }}</small>
            </button>
          </div>
        </section>
      </div>

      <footer class="modal-actions">
        <input v-model="manualPath" placeholder="Manual path" />
        <button class="secondary-button" @click="$emit('close')">Cancel</button>
        <button class="primary-button" :disabled="!manualPath" @click="$emit('select', manualPath)">Use Folder</button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ArrowUp, Folder, HardDrive, LoaderCircle, X } from 'lucide-vue-next';
import { api } from '../services/api';
import type { FilesystemEntry } from '../types';

defineEmits<{
  close: [];
  select: [path: string];
}>();

const roots = ref<FilesystemEntry[]>([]);
const entries = ref<FilesystemEntry[]>([]);
const currentPath = ref('');
const parentPath = ref<string | null>(null);
const manualPath = ref('');
const loading = ref(false);

onMounted(async () => {
  const result = await api.filesystemRoots();
  roots.value = result.roots;
  if (result.roots[0]) {
    await openPath(result.roots[0].path);
  }
});

async function openPath(path: string) {
  loading.value = true;
  currentPath.value = path;
  manualPath.value = path;
  try {
    const result = await api.filesystemChildren(path);
    entries.value = result.entries;
    parentPath.value = result.parent_path;
    currentPath.value = result.path;
    manualPath.value = result.path;
  } finally {
    loading.value = false;
  }
}
</script>
