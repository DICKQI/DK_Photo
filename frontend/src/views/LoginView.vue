<template>
  <main class="login-shell">
    <section class="login-panel">
      <div>
        <p class="eyebrow">DK Photo</p>
        <h1>家庭照片中心</h1>
        <p class="muted">登录后浏览文件夹、查看缩略图，并管理共享相册。</p>
      </div>
      <form class="login-form" @submit.prevent="submit">
        <label>
          <span>邮箱</span>
          <input v-model="email" type="email" autocomplete="email" required />
        </label>
        <label>
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
        <button class="primary-button" type="submit" :disabled="loading">
          <LogIn :size="18" />
          {{ loading ? '登录中' : '登录' }}
        </button>
        <p v-if="error" class="error-text">{{ error }}</p>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { LogIn } from 'lucide-vue-next';
import { api } from '../services/api';

const router = useRouter();
const route = useRoute();
const email = ref('admin@example.com');
const password = ref('');
const loading = ref(false);
const error = ref('');

async function submit() {
  loading.value = true;
  error.value = '';
  try {
    await api.login(email.value, password.value);
    await router.push((route.query.next as string) || '/');
  } catch (err) {
    error.value = err instanceof Error ? err.message : '登录失败';
  } finally {
    loading.value = false;
  }
}
</script>
