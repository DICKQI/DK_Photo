import { createRouter, createWebHistory } from 'vue-router';
import AlbumView from './views/AlbumView.vue';
import LoginView from './views/LoginView.vue';
import ShareView from './views/ShareView.vue';
import { api } from './services/api';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    { path: '/', name: 'album', component: AlbumView, meta: { requiresAuth: true } },
    { path: '/admin', redirect: { name: 'admin-libraries' }, meta: { requiresAuth: true, admin: true } },
    { path: '/admin/users', name: 'admin-users', component: AlbumView, meta: { requiresAuth: true, admin: true } },
    { path: '/admin/libraries', name: 'admin-libraries', component: AlbumView, meta: { requiresAuth: true, admin: true } },
    { path: '/admin/tools', name: 'admin-tools', component: AlbumView, meta: { requiresAuth: true, admin: true } },
    { path: '/admin/settings', name: 'admin-settings', component: AlbumView, meta: { requiresAuth: true, admin: true } },
    { path: '/share/:token', name: 'share', component: ShareView },
  ],
});

router.beforeEach(async (to) => {
  if (!to.meta.requiresAuth) return true;
  const user = await api.me().catch(() => null);
  if (!user) return { name: 'login', query: { next: to.fullPath } };
  if (to.meta.admin && user.role !== 'admin') return { name: 'album' };
  return true;
});

export default router;
