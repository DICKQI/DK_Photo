<template>
  <RouterView v-slot="{ Component }">
    <Transition name="page-fade" mode="out-in">
      <component :is="Component" />
    </Transition>
  </RouterView>
  <GlobalScanIndicator />
</template>

<script setup lang="ts">
import GlobalScanIndicator from './components/GlobalScanIndicator.vue';
</script>
