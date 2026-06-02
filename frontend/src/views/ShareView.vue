<template>
  <main class="share-shell">
    <header class="share-header">
      <div>
        <p class="eyebrow">Shared</p>
        <h1>{{ share?.title || '共享照片' }}</h1>
      </div>
      <span v-if="share?.expires_at">有效期至 {{ new Date(share.expires_at).toLocaleDateString() }}</span>
    </header>

    <section v-if="loading" class="empty-state">
      <LoaderCircle class="spin" :size="28" />
      正在载入分享
    </section>
    <section v-else-if="error" class="empty-state">
      <ImageOff :size="34" />
      <strong>{{ error }}</strong>
    </section>
    <section v-else class="public-grid">
      <a v-for="asset in assets" :key="asset.id" class="photo-tile" :href="publicOriginalUrl(token, asset.id)" target="_blank">
        <img :src="publicThumbnailUrl(token, asset.id, 'medium')" :alt="asset.filename" loading="lazy" />
        <span>{{ asset.filename }}</span>
      </a>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { ImageOff, LoaderCircle } from 'lucide-vue-next';
import { api, publicOriginalUrl, publicThumbnailUrl } from '../services/api';
import type { Asset, PublicShare } from '../types';

const route = useRoute();
const token = route.params.token as string;
const share = ref<PublicShare | null>(null);
const assets = ref<Asset[]>([]);
const loading = ref(true);
const error = ref('');

onMounted(async () => {
  try {
    share.value = await api.publicShare(token);
    assets.value = await api.publicShareAssets(token);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '分享不可用';
  } finally {
    loading.value = false;
  }
});
</script>
