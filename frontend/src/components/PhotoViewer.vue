<template>
  <div class="viewer" @keydown.esc="$emit('close')" tabindex="0" ref="viewerRef">
    <header class="viewer-bar">
      <button class="viewer-icon" @click="$emit('close')" title="关闭">
        <X :size="22" />
      </button>
      <div>
        <strong>{{ current.filename }}</strong>
        <span>{{ metaText }}</span>
      </div>
      <div class="viewer-actions">
        <button class="viewer-icon" @click="$emit('share', current)" title="分享">
          <Share2 :size="20" />
        </button>
        <a class="viewer-icon" :href="originalUrl(current.id)" target="_blank" title="下载原图">
          <Download :size="20" />
        </a>
      </div>
    </header>
    <button class="viewer-nav left" @click="previous" title="上一张">
      <ChevronLeft :size="28" />
    </button>
    <img class="viewer-image" :src="originalUrl(current.id)" :alt="current.filename" />
    <button class="viewer-nav right" @click="next" title="下一张">
      <ChevronRight :size="28" />
    </button>
    <aside class="info-panel">
      <p class="eyebrow">Info</p>
      <dl>
        <dt>文件</dt>
        <dd>{{ current.filename }}</dd>
        <dt>尺寸</dt>
        <dd>{{ current.width || '-' }} × {{ current.height || '-' }}</dd>
        <dt>大小</dt>
        <dd>{{ formatBytes(current.size) }}</dd>
      </dl>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { ChevronLeft, ChevronRight, Download, Share2, X } from 'lucide-vue-next';
import { originalUrl } from '../services/api';
import type { Asset } from '../types';

const props = defineProps<{
  assets: Asset[];
  index: number;
}>();

const emit = defineEmits<{
  close: [];
  'update:index': [index: number];
  share: [asset: Asset];
}>();

const viewerRef = ref<HTMLElement | null>(null);
const current = computed(() => props.assets[props.index]);
const metaText = computed(() => `${props.index + 1} / ${props.assets.length}`);

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
}

function previous() {
  emit('update:index', props.index === 0 ? props.assets.length - 1 : props.index - 1);
}

function next() {
  emit('update:index', props.index === props.assets.length - 1 ? 0 : props.index + 1);
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
</script>
