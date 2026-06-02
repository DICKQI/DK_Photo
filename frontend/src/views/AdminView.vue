<template>
  <main class="admin-shell">
    <header class="admin-header">
      <div>
        <p class="eyebrow">Admin</p>
        <h1>Management Console</h1>
      </div>
      <div class="admin-actions">
        <button class="secondary-button" @click="refreshAll">
          <RefreshCw :size="18" />
          Refresh
        </button>
        <RouterLink class="secondary-button" to="/">
          <Images :size="18" />
          Back to Photos
        </RouterLink>
      </div>
    </header>

    <section class="admin-grid">
      <article class="admin-panel wide-panel">
        <header>
          <h2>Libraries</h2>
          <button class="secondary-button" @click="showDirectoryPicker = true">
            <FolderSearch :size="17" />
            Choose Folder
          </button>
        </header>
        <form class="library-form" @submit.prevent="createLibrary">
          <input v-model="libraryName" placeholder="Library name" required />
          <input v-model="libraryPath" placeholder="C:\\Photos or /photos" required />
          <button class="primary-button" type="submit">
            <Plus :size="17" />
            Add
          </button>
        </form>
        <div class="table-list">
          <div v-for="library in libraries" :key="library.id" class="table-row library-row">
            <div>
              <strong>{{ library.name }}</strong>
              <span>{{ library.path }}</span>
            </div>
            <div class="row-actions">
              <small>{{ library.last_scan_at ? new Date(library.last_scan_at).toLocaleString() : 'Never scanned' }}</small>
              <button class="secondary-button" @click="scan(library.id)">
                <ScanLine :size="17" />
                Scan
              </button>
            </div>
          </div>
        </div>
      </article>

      <article class="admin-panel">
        <header>
          <h2>Create User</h2>
        </header>
        <form class="stack-form" @submit.prevent="createUser">
          <input v-model="newUser.email" type="email" placeholder="Email" required />
          <input v-model="newUser.displayName" placeholder="Display name" required />
          <input v-model="newUser.password" type="password" placeholder="Password, at least 8 chars" required />
          <select v-model="newUser.role" class="select-control">
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>
          <button class="primary-button" type="submit">
            <UserPlus :size="17" />
            Create User
          </button>
        </form>
      </article>

      <article class="admin-panel wide-panel">
        <header>
          <h2>Users</h2>
        </header>
        <div class="user-table">
          <div v-for="user in users" :key="user.id" class="user-card">
            <div class="user-main">
              <strong>{{ user.display_name }}</strong>
              <span>{{ user.email }}</span>
              <div class="status-row">
                <small class="status-pill" :class="{ off: !user.is_active }">{{ user.is_active ? 'Active' : 'Disabled' }}</small>
                <small class="status-pill">{{ user.role }}</small>
              </div>
            </div>
            <div class="user-controls">
              <input v-model="editBuffer[user.id].display_name" placeholder="Display name" />
              <input v-model="editBuffer[user.id].email" type="email" placeholder="Email" />
              <select v-model="editBuffer[user.id].role" class="select-control">
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
              <button class="secondary-button" @click="saveUser(user)">
                <Save :size="16" />
                Save
              </button>
              <button class="secondary-button" @click="openPasswordReset(user)">
                <KeyRound :size="16" />
                Password
              </button>
              <button class="secondary-button" @click="openPermissions(user)">
                <ShieldCheck :size="16" />
                Libraries
              </button>
              <button v-if="user.is_active" class="danger-button" @click="disableUser(user)">
                <UserX :size="16" />
                Disable
              </button>
              <button v-else class="secondary-button" @click="enableUser(user)">
                <UserCheck :size="16" />
                Enable
              </button>
            </div>
          </div>
        </div>
      </article>

      <article class="admin-panel">
        <header>
          <h2>Scan Jobs</h2>
        </header>
        <div class="table-list">
          <div v-for="job in jobs" :key="job.id" class="table-row">
            <div>
              <strong>#{{ job.id }} · {{ job.status }}</strong>
              <span>{{ job.message || 'Waiting' }}</span>
            </div>
            <small>{{ job.total_assets }} photos</small>
          </div>
        </div>
      </article>

      <article class="admin-panel">
        <header>
          <h2>Share Links</h2>
        </header>
        <div class="table-list">
          <div v-for="share in shares" :key="share.id" class="table-row">
            <div>
              <strong>{{ share.title }}</strong>
              <span>/share/{{ share.token }}</span>
            </div>
            <small>{{ share.expires_at ? new Date(share.expires_at).toLocaleDateString() : 'Never' }}</small>
          </div>
        </div>
      </article>
    </section>

    <DirectoryPicker
      v-if="showDirectoryPicker"
      @close="showDirectoryPicker = false"
      @select="selectDirectory"
    />

    <div v-if="passwordUser" class="modal-backdrop">
      <section class="small-modal">
        <header class="modal-header">
          <h2>Reset Password</h2>
          <button class="icon-button" @click="passwordUser = null">
            <X :size="18" />
          </button>
        </header>
        <input v-model="newPassword" type="password" placeholder="New password" />
        <footer class="modal-actions">
          <button class="secondary-button" @click="passwordUser = null">Cancel</button>
          <button class="primary-button" :disabled="newPassword.length < 8" @click="resetPassword">Reset</button>
        </footer>
      </section>
    </div>

    <div v-if="permissionUser" class="modal-backdrop">
      <section class="permission-modal">
        <header class="modal-header">
          <div>
            <p class="eyebrow">Permissions</p>
            <h2>{{ permissionUser.display_name }}</h2>
          </div>
          <button class="icon-button" @click="permissionUser = null">
            <X :size="18" />
          </button>
        </header>
        <div class="permission-list">
          <label v-for="library in libraries" :key="library.id" class="permission-row">
            <div>
              <strong>{{ library.name }}</strong>
              <span>{{ library.path }}</span>
            </div>
            <span class="toggle-group">
              <input v-model="permissionBuffer[library.id].can_view" type="checkbox" />
              View
            </span>
            <span class="toggle-group">
              <input v-model="permissionBuffer[library.id].can_share" type="checkbox" :disabled="!permissionBuffer[library.id].can_view" />
              Share
            </span>
          </label>
        </div>
        <footer class="modal-actions">
          <button class="secondary-button" @click="permissionUser = null">Cancel</button>
          <button class="primary-button" @click="savePermissions">Save Permissions</button>
        </footer>
      </section>
    </div>

    <p v-if="message" class="toast">{{ message }}</p>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import {
  FolderSearch,
  Images,
  KeyRound,
  Plus,
  RefreshCw,
  Save,
  ScanLine,
  ShieldCheck,
  UserCheck,
  UserPlus,
  UserX,
  X,
} from 'lucide-vue-next';
import DirectoryPicker from '../components/DirectoryPicker.vue';
import { api } from '../services/api';
import type { Library, LibraryPermission, ScanJob, ShareLink, User } from '../types';

const libraries = ref<Library[]>([]);
const jobs = ref<ScanJob[]>([]);
const users = ref<User[]>([]);
const shares = ref<ShareLink[]>([]);
const libraryName = ref('Family Photos');
const libraryPath = ref('/photos');
const message = ref('');
const showDirectoryPicker = ref(false);
const passwordUser = ref<User | null>(null);
const permissionUser = ref<User | null>(null);
const newPassword = ref('');
const newUser = reactive({ email: '', displayName: '', password: '', role: 'member' });
const editBuffer = reactive<Record<number, { email: string; display_name: string; role: 'admin' | 'member' }>>({});
const permissionBuffer = reactive<Record<number, { can_view: boolean; can_share: boolean }>>({});

onMounted(refreshAll);

async function refreshAll() {
  libraries.value = await api.libraries();
  jobs.value = await api.jobs();
  users.value = await api.users();
  shares.value = await api.adminShares();
  syncEditBuffer();
}

function syncEditBuffer() {
  for (const user of users.value) {
    editBuffer[user.id] = {
      email: user.email,
      display_name: user.display_name,
      role: user.role,
    };
  }
}

function selectDirectory(path: string) {
  libraryPath.value = path;
  showDirectoryPicker.value = false;
}

async function createLibrary() {
  await api.createLibrary(libraryName.value, libraryPath.value);
  message.value = 'Library created';
  await refreshAll();
}

async function scan(libraryId: number) {
  await api.scanLibrary(libraryId);
  message.value = 'Scan queued';
  await refreshAll();
}

async function createUser() {
  await api.createUser(newUser.email, newUser.displayName, newUser.password, newUser.role);
  Object.assign(newUser, { email: '', displayName: '', password: '', role: 'member' });
  message.value = 'User created';
  await refreshAll();
}

async function saveUser(user: User) {
  const draft = editBuffer[user.id];
  await api.updateUser(user.id, draft);
  message.value = 'User updated';
  await refreshAll();
}

function openPasswordReset(user: User) {
  passwordUser.value = user;
  newPassword.value = '';
}

async function resetPassword() {
  if (!passwordUser.value) return;
  await api.resetUserPassword(passwordUser.value.id, newPassword.value);
  message.value = 'Password reset';
  passwordUser.value = null;
}

async function disableUser(user: User) {
  await api.disableUser(user.id);
  message.value = 'User disabled';
  await refreshAll();
}

async function enableUser(user: User) {
  await api.enableUser(user.id);
  message.value = 'User enabled';
  await refreshAll();
}

async function openPermissions(user: User) {
  permissionUser.value = user;
  const permissions = await api.userPermissions(user.id);
  const byLibrary = new Map<number, LibraryPermission>();
  for (const permission of permissions) byLibrary.set(permission.library_id, permission);
  for (const library of libraries.value) {
    const permission = byLibrary.get(library.id);
    permissionBuffer[library.id] = {
      can_view: permission?.can_view ?? user.role === 'admin',
      can_share: permission?.can_share ?? user.role === 'admin',
    };
  }
}

async function savePermissions() {
  if (!permissionUser.value) return;
  const payload = libraries.value.map((library) => ({
    library_id: library.id,
    can_view: permissionBuffer[library.id]?.can_view ?? false,
    can_share: permissionBuffer[library.id]?.can_share ?? false,
  }));
  await api.updateUserPermissions(permissionUser.value.id, payload);
  message.value = 'Permissions updated';
  permissionUser.value = null;
}
</script>
