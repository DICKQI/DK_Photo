import { computed, ref } from 'vue';

type Theme = 'light' | 'dark';

const storedTheme = localStorage.getItem('dk-photo-theme') as Theme | null;
const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
const theme = ref<Theme>(storedTheme || (prefersDark ? 'dark' : 'light'));

function applyTheme(value: Theme) {
  document.documentElement.dataset.theme = value;
  document.documentElement.style.colorScheme = value;
  localStorage.setItem('dk-photo-theme', value);
}

applyTheme(theme.value);

export function useTheme() {
  const isDark = computed(() => theme.value === 'dark');

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark';
    applyTheme(theme.value);
  }

  return { isDark, theme, toggleTheme };
}
