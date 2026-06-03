<template>
  <button class="secondary-button language-toggle" type="button" :title="t('language.toggleTitle')" @click="toggleLocale">
    <Languages :size="17" />
    <span>{{ languageLabel }}</span>
  </button>
</template>

<script setup lang="ts">
import { Languages } from 'lucide-vue-next';
import { useLocale } from '../composables/useLocale';

const { languageLabel, t, toggleLocale } = useLocale();
</script>
