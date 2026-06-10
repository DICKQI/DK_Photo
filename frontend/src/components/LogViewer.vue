<template>
  <article class="admin-panel settings-panel log-viewer-panel">
    <header>
      <div>
        <h2>{{ t('admin.logViewerTitle') }}</h2>
        <p class="panel-note">{{ t('admin.logViewerNote') }}</p>
      </div>
      <div class="log-header-actions">
        <span v-if="connected" class="log-status connected">{{ t('admin.logConnected') }}</span>
        <span v-else class="log-status disconnected">{{ t('admin.logDisconnected') }}</span>
        <button class="secondary-button" @click="clearLogs">
          <Trash2 :size="16" />
          {{ t('admin.logClear') }}
        </button>
      </div>
    </header>

    <div class="log-filter-bar">
      <div class="segmented-control compact-filter">
        <button :class="{ active: levelFilter === 'ALL' }" @click="levelFilter = 'ALL'">{{ t('admin.logLevelAll') }}</button>
        <button :class="{ active: levelFilter === 'INFO' }" @click="levelFilter = 'INFO'">INFO</button>
        <button :class="{ active: levelFilter === 'WARNING' }" @click="levelFilter = 'WARNING'">WARNING</button>
        <button :class="{ active: levelFilter === 'ERROR' }" @click="levelFilter = 'ERROR'">ERROR</button>
      </div>
      <label class="search-input log-search">
        <Search :size="16" />
        <input v-model="searchText" :placeholder="t('admin.logSearchPlaceholder')" />
      </label>
      <label class="log-autoscroll">
        <input type="checkbox" v-model="autoScroll" />
        <span>{{ t('admin.logAutoScroll') }}</span>
      </label>
    </div>

    <div ref="logContainer" class="log-container">
      <div v-if="!filteredLogs.length" class="log-empty">
        <LoaderCircle v-if="connected" class="spin" :size="20" />
        <AlertCircle v-else :size="20" />
        <span>{{ connected ? t('admin.logWaiting') : t('admin.logNotConnected') }}</span>
      </div>
      <div v-else class="log-entries">
        <div
          v-for="(entry, idx) in filteredLogs"
          :key="idx"
          class="log-entry"
          :class="entry.level.toLowerCase()"
        >
          <span class="log-time">{{ entry.timestamp }}</span>
          <span class="log-level">{{ entry.level }}</span>
          <span class="log-logger">{{ entry.logger }}</span>
          <span class="log-msg">{{ entry.message }}</span>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { AlertCircle, LoaderCircle, Search, Trash2 } from 'lucide-vue-next';
import { useLocale } from '../composables/useLocale';
import { useLogStream } from '../composables/useLogStream';

const { t } = useLocale();

const { logs, connected, connect, disconnect, clearLogs } = useLogStream();
const autoScroll = ref(true);
const levelFilter = ref('ALL');
const searchText = ref('');
const logContainer = ref<HTMLElement | null>(null);

const filteredLogs = computed(() => {
  let result = logs.value;
  if (levelFilter.value !== 'ALL') {
    result = result.filter((e) => e.level === levelFilter.value);
  }
  const q = searchText.value.trim().toLowerCase();
  if (q) {
    result = result.filter(
      (e) =>
        e.message.toLowerCase().includes(q) ||
        e.logger.toLowerCase().includes(q),
    );
  }
  return result;
});

function scrollToBottom() {
  if (!autoScroll.value) return;
  nextTick(() => {
    const el = logContainer.value;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  });
}

watch(() => logs.value.length, () => {
  scrollToBottom();
});

onMounted(() => {
  connect();
});

onBeforeUnmount(() => {
  disconnect();
});
</script>

<style scoped>
.log-viewer-panel {
  margin-top: 1.5rem;
}

.log-header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.log-status {
  font-size: 0.8rem;
  padding: 2px 8px;
  border-radius: 999px;
}

.log-status.connected {
  background: rgba(34, 197, 94, 0.15);
  color: #16a34a;
}

.log-status.disconnected {
  background: rgba(239, 68, 68, 0.15);
  color: #dc2626;
}

.log-filter-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.log-search {
  flex: 1;
  min-width: 180px;
}

.log-autoscroll {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: var(--text-secondary);
  cursor: pointer;
  white-space: nowrap;
}

.log-container {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  height: 400px;
  overflow-y: auto;
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
  font-size: 0.75rem;
  line-height: 1.55;
}

.log-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  height: 100%;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.log-entries {
  padding: 0.5rem;
}

.log-entry {
  display: flex;
  gap: 0.5rem;
  padding: 2px 4px;
  border-radius: 3px;
}

.log-entry:hover {
  background: rgba(128, 128, 128, 0.08);
}

.log-entry.info .log-level {
  color: #3b82f6;
}

.log-entry.warning .log-level {
  color: #f59e0b;
}

.log-entry.error {
  background: rgba(239, 68, 68, 0.08);
}

.log-entry.error .log-level {
  color: #ef4444;
}

.log-time {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.log-level {
  font-weight: 700;
  width: 56px;
  flex-shrink: 0;
  text-align: center;
}

.log-logger {
  color: #a78bfa;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
}

.log-msg {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
