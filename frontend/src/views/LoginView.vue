<template>
  <main class="login-shell">
    <div class="login-utility-row">
      <LanguageToggle />
      <button class="login-theme-toggle icon-button" :title="t('common.toggleTheme')" @click="toggleTheme">
        <Sun v-if="isDark" :size="18" />
        <Moon v-else :size="18" />
      </button>
    </div>
    <section class="login-panel">
      <div class="login-copy">
        <div class="brand-row">
          <div class="brand-mark">DK</div>
          <div>
            <strong>DK Photo</strong>
            <span>{{ t('login.privateLibrary') }}</span>
          </div>
        </div>
        <h1>{{ t('login.title') }}</h1>
        <p class="muted">{{ t('login.subtitle') }}</p>
        <div class="login-feature-list">
          <span>
            <FolderTree :size="17" />
            {{ t('login.folderFirst') }}
          </span>
          <span>
            <Image :size="17" />
            {{ t('login.fastThumbnails') }}
          </span>
          <span>
            <ShieldCheck :size="17" />
            {{ t('login.privateSharing') }}
          </span>
        </div>
      </div>
      <form class="login-form login-card" :class="{ invalid: hasLoginError }" @submit.prevent="submit">
        <div>
          <p class="eyebrow">{{ t('login.signInEyebrow') }}</p>
          <h2>{{ t('login.openLibrary') }}</h2>
        </div>
        <div class="login-helper">
          <ShieldCheck :size="17" />
          <span>{{ t('login.helper') }}</span>
        </div>
        <label>
          <span>{{ t('login.email') }}</span>
          <span class="input-shell">
            <Mail :size="17" />
            <input v-model="email" type="email" autocomplete="email" required @input="clearError" />
          </span>
        </label>
        <label>
          <span>{{ t('login.password') }}</span>
          <span class="input-shell">
            <LockKeyhole :size="17" />
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              required
              @input="clearError"
            />
            <button class="inline-icon-button" type="button" :title="showPassword ? t('login.hidePassword') : t('login.showPassword')" @click="showPassword = !showPassword">
              <EyeOff v-if="showPassword" :size="16" />
              <Eye v-else :size="16" />
            </button>
          </span>
        </label>
        <button class="primary-button" type="submit" :disabled="loading">
          <LoaderCircle v-if="loading" class="spin" :size="18" />
          <LogIn v-else :size="18" />
          {{ loading ? t('login.signingIn') : t('login.signIn') }}
        </button>
        <p class="login-footnote">
          {{ t('login.footnote') }}
        </p>
        <p v-if="error" class="error-text login-error">
          <CircleAlert :size="16" />
          {{ error }}
        </p>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { CircleAlert, Eye, EyeOff, FolderTree, Image, LoaderCircle, LockKeyhole, LogIn, Mail, Moon, ShieldCheck, Sun } from 'lucide-vue-next';
import LanguageToggle from '../components/LanguageToggle.vue';
import { useLocale } from '../composables/useLocale';
import { useTheme } from '../composables/useTheme';
import { api } from '../services/api';

const router = useRouter();
const route = useRoute();
const { isDark, toggleTheme } = useTheme();
const { t } = useLocale();
const email = ref('admin@example.com');
const password = ref('');
const loading = ref(false);
const error = ref('');
const hasLoginError = ref(false);
const showPassword = ref(false);

async function submit() {
  loading.value = true;
  error.value = '';
  hasLoginError.value = false;
  try {
    await api.login(email.value, password.value);
    await router.push((route.query.next as string) || '/');
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('login.failed');
    triggerLoginError();
  } finally {
    loading.value = false;
  }
}

function clearError() {
  error.value = '';
  hasLoginError.value = false;
}

function triggerLoginError() {
  hasLoginError.value = false;
  window.requestAnimationFrame(() => {
    hasLoginError.value = true;
  });
}
</script>
