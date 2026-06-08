<template>
  <nav class="management-nav" :class="`management-nav-${props.variant}`" :aria-label="t('admin.managementNav')">
    <span v-if="props.showHeading" class="management-nav-title">{{ t('admin.managementGroup') }}</span>
    <RouterLink
      v-for="item in items"
      :key="item.routeName"
      :to="{ name: item.routeName }"
      :class="[linkClass, { active: isActive(item.routeName) }]"
      @click="emit('navigate')"
    >
      <component :is="item.icon" :size="iconSize" />
      <span>{{ t(item.labelKey) }}</span>
    </RouterLink>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { GalleryHorizontal, Settings, SlidersHorizontal, Users } from 'lucide-vue-next';
import { useLocale } from '../composables/useLocale';

type Variant = 'sidebar' | 'sheet';

const props = withDefaults(
  defineProps<{
    variant?: Variant;
    showHeading?: boolean;
  }>(),
  {
    variant: 'sidebar',
    showHeading: true,
  },
);

const emit = defineEmits<{
  navigate: [];
}>();

const route = useRoute();
const { t } = useLocale();
const iconSize = computed(() => 18);
const linkClass = computed(() =>
  props.variant === 'sheet' ? 'more-sheet-item management-nav-link management-nav-sheet-link' : 'admin-link management-nav-link',
);

const items = [
  { routeName: 'admin-users', labelKey: 'admin.navUsers', icon: Users },
  { routeName: 'admin-libraries', labelKey: 'admin.navLibraries', icon: GalleryHorizontal },
  { routeName: 'admin-tools', labelKey: 'admin.navTools', icon: SlidersHorizontal },
  { routeName: 'admin-settings', labelKey: 'admin.navSettings', icon: Settings },
] as const;

function isActive(routeName: string) {
  return route.name === routeName;
}
</script>
