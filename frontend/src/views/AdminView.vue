<template>
  <main class="admin-shell">
    <header class="admin-header">
      <div>
        <p class="eyebrow">{{ t('admin.eyebrow') }}</p>
        <h1>{{ t('admin.title') }}</h1>
      </div>
      <div class="admin-actions">
        <button class="secondary-button" @click="toggleTheme">
          <Sun v-if="isDark" :size="18" />
          <Moon v-else :size="18" />
          {{ t('common.theme') }}
        </button>
        <LanguageToggle />
        <button class="secondary-button" :disabled="isBusy(refreshKey)" @click="refreshAll">
          <LoaderCircle v-if="isBusy(refreshKey)" class="spin" :size="18" />
          <RefreshCw v-else :size="18" />
          {{ isBusy(refreshKey) ? t('common.refreshing') : t('common.refresh') }}
        </button>
        <RouterLink class="secondary-button" to="/">
          <Images :size="18" />
          {{ t('common.backToPhotos') }}
        </RouterLink>
      </div>
    </header>

    <section class="admin-summary-grid">
      <article class="summary-tile">
        <FolderSearch :size="20" />
        <span>{{ t('admin.summaryLibraries') }}</span>
        <strong>{{ libraries.length }}</strong>
      </article>
      <article class="summary-tile">
        <UserPlus :size="20" />
        <span>{{ t('admin.summaryActiveUsers') }}</span>
        <strong>{{ activeUserCount }}</strong>
      </article>
      <article class="summary-tile">
        <ScanLine :size="20" />
        <span>{{ t('admin.summaryRunningScans') }}</span>
        <strong>{{ runningJobCount }}</strong>
      </article>
      <article class="summary-tile">
        <ShieldCheck :size="20" />
        <span>{{ t('admin.summaryOpenShares') }}</span>
        <strong>{{ activeShareCount }}</strong>
      </article>
    </section>

    <section class="admin-grid" :class="{ working: isWorking }">
      <article class="admin-panel wide-panel">
        <header>
          <div>
            <h2>{{ t('admin.librariesTitle') }}</h2>
            <p class="panel-note">{{ t('admin.librariesNote') }}</p>
          </div>
          <button class="secondary-button" type="button" @click="showDirectoryPicker = true">
            <FolderSearch :size="17" />
            {{ t('admin.browseServer') }}
          </button>
        </header>
        <form class="library-form" @submit.prevent="createLibrary">
          <input v-model="libraryName" :placeholder="t('admin.libraryName')" required />
          <div class="path-input-wrap">
            <input v-model="libraryPath" placeholder="C:\\Photos or /photos/travel" required />
            <button class="icon-button" type="button" :title="t('admin.selectFolder')" @click="showDirectoryPicker = true">
              <FolderSearch :size="17" />
            </button>
          </div>
          <button class="primary-button" type="submit" :disabled="isBusy(createLibraryKey)">
            <LoaderCircle v-if="isBusy(createLibraryKey)" class="spin" :size="17" />
            <Plus v-else :size="17" />
            {{ isBusy(createLibraryKey) ? t('common.adding') : t('common.add') }}
          </button>
        </form>
        <div v-if="!libraries.length" class="panel-empty">
          <GalleryHorizontal :size="24" />
          <strong>{{ t('admin.noLibrariesYet') }}</strong>
          <span>{{ t('admin.noLibrariesHint') }}</span>
        </div>
        <div v-else class="toolbar-row">
          <label class="search-input">
            <Search :size="16" />
            <input v-model="librarySearch" :placeholder="t('admin.searchLibraries')" />
          </label>
        </div>
        <div v-if="libraries.length && !filteredLibraries.length" class="panel-empty">
          <GalleryHorizontal :size="24" />
          <strong>{{ t('admin.noMatchingLibraries') }}</strong>
          <span>{{ t('admin.noMatchingLibrariesHint') }}</span>
        </div>
        <div v-else class="table-list">
          <div v-for="library in filteredLibraries" :key="library.id" class="table-row library-row">
            <div class="row-title">
              <span class="row-icon">
                <FolderOpen :size="20" />
              </span>
              <div class="library-row-body">
                <input
                  v-if="editingLibraryId === library.id"
                  v-model="libraryEditBuffer[library.id]"
                  class="library-name-input"
                  :placeholder="t('admin.libraryName')"
                  @keydown.enter.prevent="saveLibraryName(library)"
                  @keydown.esc.prevent="cancelLibraryEdit"
                />
                <strong v-else>{{ library.name }}</strong>
                <span>{{ library.path }}</span>
              </div>
            </div>
            <div class="row-actions">
              <small class="status-pill neutral">{{ library.last_scan_at ? formatDateTime(library.last_scan_at) : t('common.neverScanned') }}</small>
              <template v-if="editingLibraryId === library.id">
                <button class="secondary-button" :disabled="!isLibraryNameChanged(library) || isBusy(librarySaveKey(library.id))" @click="saveLibraryName(library)">
                  <LoaderCircle v-if="isBusy(librarySaveKey(library.id))" class="spin" :size="17" />
                  <Save v-else :size="17" />
                  {{ isBusy(librarySaveKey(library.id)) ? t('common.saving') : t('common.save') }}
                </button>
                <button class="secondary-button" :disabled="isBusy(librarySaveKey(library.id))" @click="cancelLibraryEdit">
                  <X :size="17" />
                  {{ t('common.cancel') }}
                </button>
              </template>
              <button v-else class="secondary-button" :title="t('admin.editLibraryName')" @click="editLibrary(library)">
                <Pencil :size="17" />
                {{ t('common.edit') }}
              </button>
              <button class="primary-button" :disabled="isBusy(scanKey(library.id))" @click="scan(library.id)">
                <LoaderCircle v-if="isBusy(scanKey(library.id))" class="spin" :size="17" />
                <ScanLine v-else :size="17" />
                {{ isBusy(scanKey(library.id)) ? t('admin.queued') : t('admin.scan') }}
              </button>
              <button class="danger-button" :disabled="isBusy(libraryDeleteKey(library.id))" @click="openDeleteLibrary(library)">
                <LoaderCircle v-if="isBusy(libraryDeleteKey(library.id))" class="spin" :size="17" />
                <Trash2 v-else :size="17" />
                {{ t('common.delete') }}
              </button>
            </div>
          </div>
        </div>
      </article>

      <article class="admin-panel users-panel wide-panel">
          <header>
            <div>
              <h2>{{ t('admin.usersTitle') }}</h2>
              <p class="panel-note">{{ t('admin.usersNote') }}</p>
            </div>
            <div class="panel-header-actions">
              <small class="status-pill neutral">{{ formatCount(users.length, 'account') }}</small>
              <button class="primary-button panel-header-action" type="button" @click="showCreateUserModal = true">
                <UserPlus :size="17" />
                {{ t('admin.createUser') }}
              </button>
            </div>
          </header>
          <div v-if="users.length" class="user-toolbar">
            <label class="search-box user-search">
              <Search :size="17" />
              <input v-model="userSearch" :placeholder="t('admin.searchUsers')" />
              <button v-if="userSearch" class="search-clear" type="button" :title="t('admin.clearUserSearch')" @click="userSearch = ''">
                <X :size="15" />
              </button>
            </label>
            <div class="segmented-control user-filter" :aria-label="t('admin.filterUserStatus')">
              <button :class="{ active: userStatusFilter === 'all' }" @click="userStatusFilter = 'all'">{{ t('admin.all') }}</button>
              <button :class="{ active: userStatusFilter === 'active' }" @click="userStatusFilter = 'active'">{{ t('common.active') }}</button>
              <button :class="{ active: userStatusFilter === 'disabled' }" @click="userStatusFilter = 'disabled'">{{ t('common.disabled') }}</button>
            </div>
            <div class="segmented-control user-filter" :aria-label="t('admin.filterUserRole')">
              <button :class="{ active: userRoleFilter === 'all' }" @click="userRoleFilter = 'all'">{{ t('admin.allRoles') }}</button>
              <button :class="{ active: userRoleFilter === 'admin' }" @click="userRoleFilter = 'admin'">{{ t('admin.admins') }}</button>
              <button :class="{ active: userRoleFilter === 'member' }" @click="userRoleFilter = 'member'">{{ t('admin.members') }}</button>
            </div>
            <small class="user-result-count">{{ userResultSummary }}</small>
          </div>
          <div v-if="!users.length" class="panel-empty">
            <UserPlus :size="24" />
            <strong>{{ t('admin.noUsersFound') }}</strong>
            <span>{{ t('admin.noUsersHint') }}</span>
          </div>
          <div v-else-if="!filteredUsers.length" class="panel-empty">
            <Search :size="24" />
            <strong>{{ t('admin.noMatchingUsers') }}</strong>
            <span>{{ t('admin.noMatchingUsersHint') }}</span>
            <button class="secondary-button" @click="resetUserFilters">
              <X :size="17" />
              {{ t('admin.clearFilters') }}
            </button>
          </div>
          <div v-else class="user-table">
            <div v-for="(user, userIndex) in filteredUsers" :key="user.id" class="user-card" :style="{ '--user-index': userIndex }">
              <div class="user-main">
                <div class="user-identity">
                  <span class="user-avatar" :class="{ off: !user.is_active }">{{ userInitials(user) }}</span>
                  <div class="user-title">
                    <strong>{{ user.display_name }}</strong>
                    <span>{{ user.email }}</span>
                  </div>
                </div>
                <div class="status-row">
                  <small class="status-pill" :class="{ off: !user.is_active }">{{ user.is_active ? t('common.active') : t('common.disabled') }}</small>
                  <small class="status-pill">{{ roleLabel(user.role) }}</small>
                </div>
              </div>
              <div class="user-controls">
                <div class="user-fields">
                  <input v-model="editBuffer[user.id].display_name" :placeholder="t('admin.displayName')" />
                  <input v-model="editBuffer[user.id].email" type="email" :placeholder="t('login.email')" />
                  <select v-model="editBuffer[user.id].role" class="select-control">
                    <option value="member">{{ t('common.member') }}</option>
                    <option value="admin">{{ t('common.admin') }}</option>
                  </select>
                </div>
                <div class="user-action-row">
                  <button class="secondary-button" :disabled="isBusy(userSaveKey(user.id)) || !isUserChanged(user)" @click="saveUser(user)">
                    <LoaderCircle v-if="isBusy(userSaveKey(user.id))" class="spin" :size="16" />
                    <Save v-else :size="16" />
                    {{ isBusy(userSaveKey(user.id)) ? t('common.saving') : isUserChanged(user) ? t('common.save') : t('common.saved') }}
                  </button>
                  <button class="secondary-button" :disabled="isBusy(passwordKey(user.id))" @click="openPasswordReset(user)">
                    <LoaderCircle v-if="isBusy(passwordKey(user.id))" class="spin" :size="16" />
                    <KeyRound v-else :size="16" />
                    {{ t('common.password') }}
                  </button>
                  <button class="secondary-button" :disabled="isBusy(permissionLoadKey(user.id))" @click="openPermissions(user)">
                    <LoaderCircle v-if="isBusy(permissionLoadKey(user.id))" class="spin" :size="16" />
                    <ShieldCheck v-else :size="16" />
                    {{ t('admin.userLibraries') }}
                  </button>
                  <button v-if="user.is_active" class="danger-button" :disabled="isBusy(userDisableKey(user.id))" @click="disableUser(user)">
                    <LoaderCircle v-if="isBusy(userDisableKey(user.id))" class="spin" :size="16" />
                    <UserX v-else :size="16" />
                    {{ t('common.disable') }}
                  </button>
                  <template v-else>
                    <button class="secondary-button" :disabled="isBusy(userEnableKey(user.id))" @click="enableUser(user)">
                      <LoaderCircle v-if="isBusy(userEnableKey(user.id))" class="spin" :size="16" />
                      <UserCheck v-else :size="16" />
                      {{ t('common.enable') }}
                    </button>
                    <button class="danger-button" :disabled="isBusy(userDeleteKey(user.id))" @click="openDeleteUser(user)">
                      <LoaderCircle v-if="isBusy(userDeleteKey(user.id))" class="spin" :size="16" />
                      <Trash2 v-else :size="16" />
                      {{ t('common.delete') }}
                    </button>
                  </template>
                </div>
              </div>
            </div>
          </div>
      </article>

      <div class="admin-grid-row admin-monitor-grid">
      <article class="admin-panel monitor-panel">
        <header>
          <h2>{{ t('admin.scanJobs') }}</h2>
        </header>
        <div v-if="!jobs.length" class="panel-empty">
          <ScanLine :size="24" />
          <strong>{{ t('admin.noScanJobs') }}</strong>
          <span>{{ t('admin.noScanJobsHint') }}</span>
        </div>
        <template v-else>
          <div class="toolbar-row">
            <label class="search-input">
              <Search :size="16" />
              <input v-model="jobSearch" :placeholder="t('admin.searchScanJobs')" />
            </label>
            <div class="segmented-control compact-filter" :aria-label="t('admin.filterJobStatus')">
              <button :class="{ active: jobStatusFilter === 'all' }" @click="jobStatusFilter = 'all'">{{ t('admin.allStatuses') }}</button>
              <button :class="{ active: jobStatusFilter === 'running' }" @click="jobStatusFilter = 'running'">{{ t('admin.statusRunning') }}</button>
              <button :class="{ active: jobStatusFilter === 'queued' }" @click="jobStatusFilter = 'queued'">{{ t('admin.statusQueued') }}</button>
              <button :class="{ active: jobStatusFilter === 'completed' }" @click="jobStatusFilter = 'completed'">{{ t('admin.statusFinished') }}</button>
              <button :class="{ active: jobStatusFilter === 'failed' }" @click="jobStatusFilter = 'failed'">{{ t('admin.statusFailed') }}</button>
            </div>
          </div>
          <div v-if="!filteredJobs.length" class="panel-empty">
            <Search :size="24" />
            <strong>{{ t('admin.noMatchingScanJobs') }}</strong>
            <span>{{ t('admin.noMatchingScanJobsHint') }}</span>
          </div>
          <div v-else class="table-list scrollable">
            <div v-for="job in filteredJobs" :key="job.id" class="table-row" :class="{ 'failed-row': job.status === 'failed', 'running-row': job.status === 'running' || job.status === 'queued' }">
              <div class="row-title">
                <span class="row-icon" :class="jobStatusClass(job.status)">
                  <LoaderCircle v-if="job.status === 'running' || job.status === 'queued'" class="spin" :size="20" />
                  <CircleCheck v-else-if="job.status === 'completed'" :size="20" />
                  <CircleAlert v-else-if="job.status === 'failed'" :size="20" />
                  <CircleCheck v-else :size="20" />
                </span>
                <div>
                  <strong>#{{ job.id }} - {{ job.library_id ? libraryNameById(job.library_id) : t('admin.summaryLibraries') }}</strong>
                  <span>{{ job.message || t('common.waiting') }}</span>
                </div>
              </div>
              <div class="row-actions">
                <small class="status-pill" :class="jobStatusClass(job.status)">{{ jobStatusLabel(job.status) }}</small>
                <button
                  v-if="job.status === 'running' || job.status === 'queued'"
                  class="icon-button danger"
                  :title="t('admin.cancelScan')"
                  :disabled="isBusy(cancelJobKey(job.id))"
                  @click="cancelScan(job.id)"
                >
                  <LoaderCircle v-if="isBusy(cancelJobKey(job.id))" class="spin" :size="16" />
                  <Ban v-else :size="16" />
                </button>
                <small v-if="job.status === 'running' || job.status === 'queued'">
                  <LoaderCircle class="spin" :size="12" />
                  {{ t('admin.scanningProgress', { count: job.processed_assets.toLocaleString() }) }}
                </small>
                <small v-else>{{ formatCount(job.total_assets, 'media') }}</small>
                <small class="muted">{{ jobTimeLabel(job) }}</small>
              </div>
            </div>
          </div>
        </template>
      </article>

      <article class="admin-panel monitor-panel">
        <header>
          <h2>{{ t('admin.shareLinks') }}</h2>
        </header>
        <div v-if="!shares.length" class="panel-empty">
          <ShieldCheck :size="24" />
          <strong>{{ t('admin.noShares') }}</strong>
          <span>{{ t('admin.noSharesHint') }}</span>
        </div>
        <template v-else>
          <div class="toolbar-row">
            <label class="search-input">
              <Search :size="16" />
              <input v-model="shareSearch" :placeholder="t('admin.searchShares')" />
            </label>
            <div class="segmented-control compact-filter" :aria-label="t('admin.filterShareStatus')">
              <button :class="{ active: shareStatusFilter === 'all' }" @click="shareStatusFilter = 'all'">{{ t('admin.allShareStatuses') }}</button>
              <button :class="{ active: shareStatusFilter === 'active' }" @click="shareStatusFilter = 'active'">{{ t('admin.shareStatusActive') }}</button>
              <button :class="{ active: shareStatusFilter === 'expiring' }" @click="shareStatusFilter = 'expiring'">{{ t('album.shareStatusExpiring') }}</button>
              <button :class="{ active: shareStatusFilter === 'expired' }" @click="shareStatusFilter = 'expired'">{{ t('admin.shareStatusExpired') }}</button>
              <button :class="{ active: shareStatusFilter === 'never' }" @click="shareStatusFilter = 'never'">{{ t('album.shareStatusNever') }}</button>
              <button :class="{ active: shareStatusFilter === 'revoked' }" @click="shareStatusFilter = 'revoked'">{{ t('album.shareRevoked') }}</button>
            </div>
          </div>
          <div v-if="!filteredShares.length" class="panel-empty">
            <Search :size="24" />
            <strong>{{ t('admin.noMatchingShares') }}</strong>
            <span>{{ t('admin.noMatchingSharesHint') }}</span>
          </div>
          <div v-else class="table-list scrollable">
            <div v-for="share in filteredShares" :key="share.id" class="table-row compact">
              <div class="row-title compact-title">
                <span class="row-icon compact-icon">
                  <ShieldCheck :size="16" />
                </span>
                <div>
                  <strong>{{ share.title }}</strong>
                  <span>/share/{{ share.token }}</span>
                  <span>{{ shareScopeLabel(share) }}</span>
                </div>
              </div>
              <div class="row-actions">
                <small class="status-pill" :class="shareStatusClass(share)">{{ shareStatusLabel(share) }}</small>
                <button class="icon-button compact-btn" :title="t('common.copy')" @click="copyShareLink(share)">
                  <Copy :size="15" />
                </button>
                <button class="icon-button compact-btn" :title="t('common.edit')" :disabled="!!share.revoked_at" @click="openEditShare(share)">
                  <Pencil :size="15" />
                </button>
                <button class="icon-button compact-btn" :title="t('common.delete')" :disabled="!!share.revoked_at" @click="openDeleteShare(share)">
                  <Trash2 :size="15" />
                </button>
              </div>
            </div>
          </div>
        </template>
      </article>
      </div>
    </section>

    <DirectoryPicker
      v-if="showDirectoryPicker"
      @close="showDirectoryPicker = false"
      @select="selectDirectory"
    />

    <div v-if="showCreateUserModal" class="modal-backdrop" @click="closeCreateUserModal">
      <section class="small-modal create-user-modal" @click.stop>
        <header class="modal-header">
          <div>
            <h2>{{ t('admin.createUserTitle') }}</h2>
            <p class="panel-note">{{ t('admin.noUsersHint') }}</p>
          </div>
          <button class="icon-button" :disabled="isBusy(createUserKey)" @click="closeCreateUserModal">
            <X :size="18" />
          </button>
        </header>
        <form class="stack-form create-user-form" @submit.prevent="createUser">
          <input v-model="newUser.email" type="email" :placeholder="t('login.email')" required />
          <input v-model="newUser.displayName" :placeholder="t('admin.displayName')" required />
          <input v-model="newUser.password" type="password" :placeholder="t('admin.passwordPlaceholder')" required />
          <select v-model="newUser.role" class="select-control">
            <option value="member">{{ t('common.member') }}</option>
            <option value="admin">{{ t('common.admin') }}</option>
          </select>
          <footer class="modal-actions create-user-actions">
            <button class="secondary-button" type="button" :disabled="isBusy(createUserKey)" @click="closeCreateUserModal">
              {{ t('common.cancel') }}
            </button>
            <button class="primary-button" type="submit" :disabled="isBusy(createUserKey)">
              <LoaderCircle v-if="isBusy(createUserKey)" class="spin" :size="17" />
              <UserPlus v-else :size="17" />
              {{ isBusy(createUserKey) ? t('common.creating') : t('admin.createUser') }}
            </button>
          </footer>
        </form>
      </section>
    </div>

    <div v-if="editShareTarget" class="modal-backdrop" @click="closeEditShare">
      <section class="small-modal" @click.stop>
        <header class="modal-header">
          <h2>{{ t('album.editShareLink') }}</h2>
          <button class="icon-button" @click="closeEditShare">
            <X :size="18" />
          </button>
        </header>
        <label class="rename-label">{{ t('album.shareTitleLabel') }}</label>
        <input v-model="editShareTitle" type="text" class="rename-input" maxlength="160" @keydown.escape="closeEditShare" />
        <label class="rename-label" style="margin-top: 0.75rem">{{ t('album.shareExpiryLabel') }}</label>
        <select v-model="editShareExpiry" class="rename-input">
          <option :value="1">{{ t('album.shareExpiry1Day') }}</option>
          <option :value="7">{{ t('album.shareExpiry7Days') }}</option>
          <option :value="30">{{ t('album.shareExpiry30Days') }}</option>
          <option :value="90">{{ t('album.shareExpiry90Days') }}</option>
          <option :value="365">{{ t('album.shareExpiry365Days') }}</option>
          <option :value="0">{{ t('album.shareExpiryNever') }}</option>
        </select>
        <label class="rename-label" style="margin-top: 0.75rem">{{ t('album.sharePasswordLabel') }}</label>
        <input v-model="editSharePassword" type="password" class="rename-input" maxlength="128" :placeholder="t('album.sharePasswordPlaceholder')" @keydown.escape="closeEditShare" />
        <footer class="modal-actions">
          <button class="secondary-button" @click="closeEditShare">{{ t('common.cancel') }}</button>
          <button class="primary-button" @click="confirmEditShare">{{ t('common.save') }}</button>
        </footer>
      </section>
    </div>

    <div v-if="deleteShareTarget" class="modal-backdrop" @click="closeDeleteShare">
      <section class="small-modal" @click.stop>
        <header class="modal-header">
          <h2>{{ t('common.delete') }}</h2>
          <button class="icon-button" @click="closeDeleteShare">
            <X :size="18" />
          </button>
        </header>
        <p>{{ t('album.confirmDeleteShare') }}</p>
        <footer class="modal-actions">
          <button class="secondary-button" @click="closeDeleteShare">{{ t('common.cancel') }}</button>
          <button class="danger-button" @click="confirmDeleteShare">{{ t('common.delete') }}</button>
        </footer>
      </section>
    </div>

    <div v-if="deleteLibraryTarget" class="modal-backdrop">
      <section class="small-modal">
        <header class="modal-header">
          <h2>{{ t('admin.deleteLibrary') }}</h2>
          <button class="icon-button" :disabled="isBusy(libraryDeleteKey(deleteLibraryTarget.id))" @click="closeDeleteLibrary">
            <X :size="18" />
          </button>
        </header>
        <div class="delete-library-summary">
          <strong>{{ deleteLibraryTarget.name }}</strong>
          <span>{{ deleteLibraryTarget.path }}</span>
          <p>{{ t('admin.deleteLibraryWarning') }}</p>
        </div>
        <footer class="modal-actions">
          <button class="secondary-button" :disabled="isBusy(libraryDeleteKey(deleteLibraryTarget.id))" @click="closeDeleteLibrary">{{ t('common.cancel') }}</button>
          <button class="danger-button" :disabled="isBusy(libraryDeleteKey(deleteLibraryTarget.id))" @click="deleteLibrary">
            <LoaderCircle v-if="isBusy(libraryDeleteKey(deleteLibraryTarget.id))" class="spin" :size="17" />
            <Trash2 v-else :size="17" />
            {{ isBusy(libraryDeleteKey(deleteLibraryTarget.id)) ? t('admin.deletingLibrary') : t('admin.confirmDeleteLibrary') }}
          </button>
        </footer>
      </section>
    </div>

    <div v-if="passwordUser" class="modal-backdrop">
      <section class="small-modal">
        <header class="modal-header">
          <h2>{{ t('admin.resetPassword') }}</h2>
          <button class="icon-button" :disabled="isBusy(passwordKey(passwordUser.id))" @click="closePasswordReset">
            <X :size="18" />
          </button>
        </header>
        <input v-model="newPassword" type="password" :placeholder="t('admin.newPassword')" />
        <footer class="modal-actions">
          <button class="secondary-button" :disabled="isBusy(passwordKey(passwordUser.id))" @click="closePasswordReset">{{ t('common.cancel') }}</button>
          <button class="primary-button" :disabled="newPassword.length < 8 || isBusy(passwordKey(passwordUser.id))" @click="resetPassword">
            <LoaderCircle v-if="isBusy(passwordKey(passwordUser.id))" class="spin" :size="17" />
            {{ isBusy(passwordKey(passwordUser.id)) ? t('admin.resetting') : t('admin.reset') }}
          </button>
        </footer>
      </section>
    </div>

    <div v-if="deleteUserTarget" class="modal-backdrop">
      <section class="small-modal">
        <header class="modal-header">
          <h2>{{ t('admin.deleteUser') }}</h2>
          <button class="icon-button" :disabled="isBusy(userDeleteKey(deleteUserTarget.id))" @click="closeDeleteUser">
            <X :size="18" />
          </button>
        </header>
        <div class="delete-library-summary">
          <strong>{{ deleteUserTarget.display_name }}</strong>
          <span>{{ deleteUserTarget.email }}</span>
          <p>{{ t('admin.deleteUserWarning') }}</p>
        </div>
        <footer class="modal-actions">
          <button class="secondary-button" :disabled="isBusy(userDeleteKey(deleteUserTarget.id))" @click="closeDeleteUser">{{ t('common.cancel') }}</button>
          <button class="danger-button" :disabled="isBusy(userDeleteKey(deleteUserTarget.id))" @click="confirmDeleteUser">
            <LoaderCircle v-if="isBusy(userDeleteKey(deleteUserTarget.id))" class="spin" :size="17" />
            <Trash2 v-else :size="17" />
            {{ isBusy(userDeleteKey(deleteUserTarget.id)) ? t('admin.deletingUser') : t('admin.confirmDeleteUser') }}
          </button>
        </footer>
      </section>
    </div>

    <div v-if="permissionUser" class="modal-backdrop">
      <section class="permission-modal">
        <header class="modal-header">
          <div>
            <p class="eyebrow">{{ t('admin.permissions') }}</p>
            <h2>{{ permissionUser.display_name }}</h2>
          </div>
          <button class="icon-button" :disabled="isBusy(permissionSaveKey(permissionUser.id))" @click="closePermissions">
            <X :size="18" />
          </button>
        </header>
        <div v-if="permissionLoading" class="panel-empty permission-empty">
          <LoaderCircle class="spin" :size="24" />
          <strong>{{ t('admin.loadingAccess') }}</strong>
          <span>{{ t('admin.loadingAccessHint') }}</span>
        </div>
        <div v-else-if="!libraries.length" class="panel-empty permission-empty">
          <FolderSearch :size="24" />
          <strong>{{ t('admin.noLibrariesToAssign') }}</strong>
          <span>{{ t('admin.noLibrariesToAssignHint') }}</span>
        </div>
        <div v-else class="permission-list">
          <div v-for="library in libraries" :key="library.id" class="permission-row">
            <div>
              <strong>{{ library.name }}</strong>
              <span>{{ library.path }}</span>
            </div>
            <label class="toggle-group switch-toggle">
              <input v-model="permissionBuffer[library.id].can_view" type="checkbox" @change="syncPermissionShare(library.id)" />
              <span class="switch-track" aria-hidden="true"></span>
              <span>{{ t('common.view') }}</span>
            </label>
            <label class="toggle-group switch-toggle">
              <input v-model="permissionBuffer[library.id].can_share" type="checkbox" :disabled="!permissionBuffer[library.id].can_view" />
              <span class="switch-track" aria-hidden="true"></span>
              <span>{{ t('admin.sharePermission') }}</span>
            </label>
          </div>
        </div>
        <footer class="modal-actions">
          <button class="secondary-button" :disabled="isBusy(permissionSaveKey(permissionUser.id))" @click="closePermissions">{{ t('common.cancel') }}</button>
          <button class="primary-button" :disabled="permissionLoading || isBusy(permissionSaveKey(permissionUser.id)) || !libraries.length" @click="savePermissions">
            <LoaderCircle v-if="isBusy(permissionSaveKey(permissionUser.id))" class="spin" :size="17" />
            {{ isBusy(permissionSaveKey(permissionUser.id)) ? t('common.saving') : t('admin.savePermissions') }}
          </button>
        </footer>
      </section>
    </div>

    <p v-if="message" class="toast" :class="messageKind">
      <CircleAlert v-if="messageKind === 'error'" :size="17" />
      <CircleCheck v-else :size="17" />
      {{ message }}
    </p>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import {
  Ban,
  CircleAlert,
  CircleCheck,
  Copy,
  FolderSearch,
  FolderOpen,
  GalleryHorizontal,
  Images,
  KeyRound,
  LoaderCircle,
  Moon,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  ScanLine,
  Search,
  ShieldCheck,
  Sun,
  Trash2,
  UserCheck,
  UserPlus,
  UserX,
  X,
} from 'lucide-vue-next';
import DirectoryPicker from '../components/DirectoryPicker.vue';
import LanguageToggle from '../components/LanguageToggle.vue';
import { useLocale } from '../composables/useLocale';
import { useTheme } from '../composables/useTheme';
import { api } from '../services/api';
import type { Library, LibraryPermission, ScanJob, ShareLink, User } from '../types';

const libraries = ref<Library[]>([]);
const { isDark, toggleTheme } = useTheme();
const { t, formatCount, formatDate, formatDateTime } = useLocale();
const jobs = ref<ScanJob[]>([]);
const users = ref<User[]>([]);
const shares = ref<ShareLink[]>([]);
const libraryName = ref('Family Photos');
const libraryPath = ref('');
const message = ref('');
const messageKind = ref<'success' | 'error'>('success');
const librarySearch = ref('');
const userSearch = ref('');
const shareSearch = ref('');
const jobSearch = ref('');
const userStatusFilter = ref<'all' | 'active' | 'disabled'>('all');
const userRoleFilter = ref<'all' | 'admin' | 'member'>('all');
const jobStatusFilter = ref<'all' | 'running' | 'queued' | 'completed' | 'failed'>('all');
const shareStatusFilter = ref<'all' | 'active' | 'expiring' | 'expired' | 'never' | 'revoked'>('all');
const editShareTarget = ref<ShareLink | null>(null);
const editShareTitle = ref('');
const editShareExpiry = ref(7);
const editSharePassword = ref<string | undefined>(undefined);
const deleteShareTarget = ref<ShareLink | null>(null);
const editingLibraryId = ref<number | null>(null);
const refreshKey = 'refresh';
const createLibraryKey = 'library:create';
const createUserKey = 'user:create';
const busyKeys = reactive<Record<string, boolean>>({});
const showDirectoryPicker = ref(false);
const showCreateUserModal = ref(false);
const passwordUser = ref<User | null>(null);
const permissionUser = ref<User | null>(null);
const deleteLibraryTarget = ref<Library | null>(null);
const deleteUserTarget = ref<User | null>(null);
const newPassword = ref('');
const newUser = reactive({ email: '', displayName: '', password: '', role: 'member' });
const libraryEditBuffer = reactive<Record<number, string>>({});
const editBuffer = reactive<Record<number, { email: string; display_name: string; role: 'admin' | 'member' }>>({});
const permissionBuffer = reactive<Record<number, { can_view: boolean; can_share: boolean }>>({});
let messageTimer: ReturnType<typeof setTimeout> | null = null;

const activeUserCount = computed(() => users.value.filter((user) => user.is_active).length);
const runningJobCount = computed(() => jobs.value.filter((job) => ['queued', 'running'].includes(job.status)).length);
const activeShareCount = computed(() => shares.value.filter((share) => !share.revoked_at && !isShareExpired(share)).length);
const isWorking = computed(() => Object.keys(busyKeys).length > 0);
const permissionLoading = computed(() => (permissionUser.value ? isBusy(permissionLoadKey(permissionUser.value.id)) : false));
const filteredLibraries = computed(() => {
  const query = librarySearch.value.trim().toLowerCase();
  if (!query) return libraries.value;
  return libraries.value.filter((library) => librarySearchText(library).includes(query));
});
const filteredUsers = computed(() => {
  const query = userSearch.value.trim().toLowerCase();
  return users.value.filter((user) => {
    const matchesQuery = !query || `${user.display_name} ${user.email}`.toLowerCase().includes(query);
    const matchesStatus =
      userStatusFilter.value === 'all' ||
      (userStatusFilter.value === 'active' && user.is_active) ||
      (userStatusFilter.value === 'disabled' && !user.is_active);
    const matchesRole = userRoleFilter.value === 'all' || user.role === userRoleFilter.value;
    return matchesQuery && matchesStatus && matchesRole;
  });
});
const filteredShares = computed(() => {
  const query = shareSearch.value.trim().toLowerCase();
  return shares.value.filter((share) => {
    const matchesQuery = !query || shareSearchText(share).includes(query);
    const matchesStatus = shareMatchesStatus(share);
    return matchesQuery && matchesStatus;
  });
});
const filteredJobs = computed(() => {
  const query = jobSearch.value.trim().toLowerCase();
  return jobs.value.filter((job) => {
    const matchesStatus = jobStatusFilter.value === 'all' || job.status === jobStatusFilter.value;
    const matchesQuery = !query || jobSearchText(job).includes(query);
    return matchesStatus && matchesQuery;
  });
});
const userResultSummary = computed(() => {
  if (!users.value.length) return t('admin.noAccounts');
  if (filteredUsers.value.length === users.value.length) return t('admin.shown', { count: users.value.length });
  return t('admin.shownPartial', { shown: filteredUsers.value.length, total: users.value.length });
});

onMounted(refreshAll);

const POLL_INTERVAL = 3000;
let pollTimer: ReturnType<typeof setInterval> | null = null;

function startJobPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    try {
      jobs.value = await api.jobs();
    } catch {
      stopJobPolling();
    }
  }, POLL_INTERVAL);
}

function stopJobPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

watch(
  () => runningJobCount.value,
  (count) => {
    if (count > 0) {
      startJobPolling();
    } else {
      stopJobPolling();
    }
  },
  { immediate: true },
);

onUnmounted(stopJobPolling);

async function refreshAll() {
  startBusy(refreshKey);
  try {
    await loadAdminData();
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableRefresh')), 'error');
  } finally {
    stopBusy(refreshKey);
  }
}

async function loadAdminData() {
  libraries.value = await api.libraries();
  jobs.value = await api.jobs();
  users.value = await api.users();
  shares.value = await api.adminShares();
  syncLibraryEditBuffer();
  syncEditBuffer();
}

function syncLibraryEditBuffer() {
  const libraryIds = new Set(libraries.value.map((library) => library.id));
  for (const library of libraries.value) libraryEditBuffer[library.id] = library.name;
  for (const key of Object.keys(libraryEditBuffer)) {
    if (!libraryIds.has(Number(key))) delete libraryEditBuffer[Number(key)];
  }
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
  libraryName.value = path.replace(/\\/g, '/').split('/').filter(Boolean).pop() || '';
  showDirectoryPicker.value = false;
}

async function createLibrary() {
  startBusy(createLibraryKey);
  try {
    await api.createLibrary(libraryName.value, libraryPath.value);
    await reloadAfterMutation(t('admin.libraryCreated'));
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableCreateLibrary')), 'error');
  } finally {
    stopBusy(createLibraryKey);
  }
}

function editLibrary(library: Library) {
  editingLibraryId.value = library.id;
  libraryEditBuffer[library.id] = library.name;
}

function cancelLibraryEdit() {
  if (editingLibraryId.value) {
    const library = libraries.value.find((item) => item.id === editingLibraryId.value);
    if (library) libraryEditBuffer[library.id] = library.name;
  }
  editingLibraryId.value = null;
}

async function saveLibraryName(library: Library) {
  const key = librarySaveKey(library.id);
  const name = libraryEditBuffer[library.id]?.trim() ?? '';
  if (!name) {
    showMessage(t('admin.libraryNameRequired'), 'error');
    return;
  }
  if (!isLibraryNameChanged(library)) return;
  startBusy(key);
  try {
    await api.updateLibrary(library.id, { name });
    editingLibraryId.value = null;
    await reloadAfterMutation(t('admin.libraryUpdated'));
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableUpdateLibrary')), 'error');
  } finally {
    stopBusy(key);
  }
}

function openDeleteLibrary(library: Library) {
  deleteLibraryTarget.value = library;
}

function closeDeleteLibrary() {
  if (deleteLibraryTarget.value && isBusy(libraryDeleteKey(deleteLibraryTarget.value.id))) return;
  deleteLibraryTarget.value = null;
}

async function deleteLibrary() {
  const library = deleteLibraryTarget.value;
  if (!library) return;
  const key = libraryDeleteKey(library.id);
  startBusy(key);
  try {
    await api.deleteLibrary(library.id);
    deleteLibraryTarget.value = null;
    if (editingLibraryId.value === library.id) editingLibraryId.value = null;
    await reloadAfterMutation(t('admin.libraryDeleted'));
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableDeleteLibrary')), 'error');
  } finally {
    stopBusy(key);
  }
}

async function scan(libraryId: number) {
  const key = scanKey(libraryId);
  startBusy(key);
  try {
    await api.scanLibrary(libraryId);
    await reloadAfterMutation(t('admin.scanQueued'));
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableQueueScan')), 'error');
  } finally {
    stopBusy(key);
  }
}

async function cancelScan(jobId: number) {
  const key = cancelJobKey(jobId);
  startBusy(key);
  try {
    await api.cancelScanJob(jobId);
    await reloadAfterMutation(t('admin.scanCancelled'));
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableCancelScan')), 'error');
  } finally {
    stopBusy(key);
  }
}

async function createUser() {
  startBusy(createUserKey);
  try {
    await api.createUser(newUser.email, newUser.displayName, newUser.password, newUser.role);
    resetNewUserForm();
    showCreateUserModal.value = false;
    await reloadAfterMutation(t('admin.userCreated'));
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableCreateUser')), 'error');
  } finally {
    stopBusy(createUserKey);
  }
}

function closeCreateUserModal() {
  if (isBusy(createUserKey)) return;
  showCreateUserModal.value = false;
  resetNewUserForm();
}

function resetNewUserForm() {
  Object.assign(newUser, { email: '', displayName: '', password: '', role: 'member' });
}

async function saveUser(user: User) {
  const key = userSaveKey(user.id);
  startBusy(key);
  try {
    const draft = editBuffer[user.id];
    await api.updateUser(user.id, {
      display_name: draft.display_name.trim(),
      email: draft.email.trim(),
      role: draft.role,
    });
    await reloadAfterMutation(t('admin.userUpdated'));
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableUpdateUser')), 'error');
  } finally {
    stopBusy(key);
  }
}

function openPasswordReset(user: User) {
  passwordUser.value = user;
  newPassword.value = '';
}

function closePasswordReset() {
  if (passwordUser.value && isBusy(passwordKey(passwordUser.value.id))) return;
  passwordUser.value = null;
}

async function resetPassword() {
  if (!passwordUser.value) return;
  const key = passwordKey(passwordUser.value.id);
  startBusy(key);
  try {
    await api.resetUserPassword(passwordUser.value.id, newPassword.value);
    showMessage(t('admin.passwordReset'));
    passwordUser.value = null;
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableResetPassword')), 'error');
  } finally {
    stopBusy(key);
  }
}

async function disableUser(user: User) {
  const key = userDisableKey(user.id);
  startBusy(key);
  try {
    await api.disableUser(user.id);
    await reloadAfterMutation(t('admin.userDisabled'));
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableDisableUser')), 'error');
  } finally {
    stopBusy(key);
  }
}

async function enableUser(user: User) {
  const key = userEnableKey(user.id);
  startBusy(key);
  try {
    await api.enableUser(user.id);
    await reloadAfterMutation(t('admin.userEnabled'));
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableEnableUser')), 'error');
  } finally {
    stopBusy(key);
  }
}

function openDeleteUser(user: User) {
  deleteUserTarget.value = user;
}

function closeDeleteUser() {
  if (deleteUserTarget.value && isBusy(userDeleteKey(deleteUserTarget.value.id))) return;
  deleteUserTarget.value = null;
}

async function confirmDeleteUser() {
  const user = deleteUserTarget.value;
  if (!user) return;
  const key = userDeleteKey(user.id);
  startBusy(key);
  try {
    await api.deleteUser(user.id);
    deleteUserTarget.value = null;
    await reloadAfterMutation(t('admin.userDeleted'));
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableDeleteUser')), 'error');
  } finally {
    stopBusy(key);
  }
}

async function openPermissions(user: User) {
  const key = permissionLoadKey(user.id);
  startBusy(key);
  permissionUser.value = user;
  clearPermissionBuffer();
  try {
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
  } catch (err) {
    permissionUser.value = null;
    showMessage(errorMessage(err, t('admin.unableLoadPermissions')), 'error');
  } finally {
    stopBusy(key);
  }
}

function closePermissions() {
  if (permissionUser.value && isBusy(permissionSaveKey(permissionUser.value.id))) return;
  permissionUser.value = null;
}

async function savePermissions() {
  if (!permissionUser.value) return;
  const key = permissionSaveKey(permissionUser.value.id);
  startBusy(key);
  try {
    const payload = libraries.value.map((library) => ({
      library_id: library.id,
      can_view: permissionBuffer[library.id]?.can_view ?? false,
      can_share: Boolean(permissionBuffer[library.id]?.can_view && permissionBuffer[library.id]?.can_share),
    }));
    await api.updateUserPermissions(permissionUser.value.id, payload);
    showMessage(t('admin.permissionsUpdated'));
    permissionUser.value = null;
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableUpdatePermissions')), 'error');
  } finally {
    stopBusy(key);
  }
}

async function reloadAfterMutation(successMessage: string) {
  showMessage(successMessage);
  try {
    await loadAdminData();
  } catch (err) {
    showMessage(errorMessage(err, t('admin.savedButReloadFailed')), 'error');
  }
}

function clearPermissionBuffer() {
  for (const key of Object.keys(permissionBuffer)) delete permissionBuffer[Number(key)];
}

function syncPermissionShare(libraryId: number) {
  if (!permissionBuffer[libraryId]?.can_view) permissionBuffer[libraryId].can_share = false;
}

function resetUserFilters() {
  userSearch.value = '';
  userStatusFilter.value = 'all';
  userRoleFilter.value = 'all';
}

function isUserChanged(user: User) {
  const draft = editBuffer[user.id];
  if (!draft) return false;
  return draft.display_name.trim() !== user.display_name || draft.email.trim() !== user.email || draft.role !== user.role;
}

function isLibraryNameChanged(library: Library) {
  const draft = libraryEditBuffer[library.id];
  return Boolean(draft?.trim()) && draft.trim() !== library.name;
}

function userInitials(user: User) {
  const source = user.display_name.trim() || user.email.trim();
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

function isBusy(key: string) {
  return Boolean(busyKeys[key]);
}

function startBusy(key: string) {
  busyKeys[key] = true;
}

function stopBusy(key: string) {
  delete busyKeys[key];
}

function scanKey(id: number) {
  return `library:scan:${id}`;
}

function cancelJobKey(id: number) {
  return `job:cancel:${id}`;
}

function librarySaveKey(id: number) {
  return `library:save:${id}`;
}

function libraryDeleteKey(id: number) {
  return `library:delete:${id}`;
}

function userSaveKey(id: number) {
  return `user:save:${id}`;
}

function passwordKey(id: number) {
  return `user:password:${id}`;
}

function permissionLoadKey(id: number) {
  return `permissions:load:${id}`;
}

function permissionSaveKey(id: number) {
  return `permissions:save:${id}`;
}

function userDisableKey(id: number) {
  return `user:disable:${id}`;
}

function userEnableKey(id: number) {
  return `user:enable:${id}`;
}

function userDeleteKey(id: number) {
  return `user:delete:${id}`;
}

function showMessage(value: string, kind: 'success' | 'error' = 'success') {
  message.value = value;
  messageKind.value = kind;
  if (messageTimer) window.clearTimeout(messageTimer);
  messageTimer = window.setTimeout(() => {
    message.value = '';
  }, kind === 'error' ? 5200 : 3200);
}

function errorMessage(err: unknown, fallback: string) {
  return err instanceof Error ? err.message : fallback;
}

function jobStatusClass(status: string) {
  if (status === 'completed') return 'success';
  if (status === 'failed') return 'off';
  if (status === 'running' || status === 'queued') return 'active';
  return 'neutral';
}

function libraryNameById(libraryId: number) {
  return libraries.value.find((library) => library.id === libraryId)?.name ?? t('admin.libraryFallback', { id: libraryId });
}

function librarySearchText(library: Library) {
  return [library.name, library.path, library.last_scan_at ? formatDateTime(library.last_scan_at) : t('common.neverScanned')].join(' ').toLowerCase();
}

function jobTimeLabel(job: ScanJob) {
  if (job.finished_at) return t('admin.jobFinished', { time: formatDateTime(job.finished_at) });
  if (job.started_at) return t('admin.jobStarted', { time: formatDateTime(job.started_at) });
  return t('common.notStarted');
}

function jobSearchText(job: ScanJob) {
  const libraryName = job.library_id ? libraryNameById(job.library_id) : t('admin.summaryLibraries');
  return [
    `#${job.id}`,
    libraryName,
    jobStatusLabel(job.status),
    job.status,
    job.message || t('common.waiting'),
    formatCount(job.total_assets, 'media'),
    jobTimeLabel(job),
  ]
    .join(' ')
    .toLowerCase();
}

function shareScopeLabel(share: ShareLink) {
  if (share.share_kind === 'asset') return t('album.shareSingleAsset');
  if (share.share_kind === 'folder') return t('album.shareFolder');
  return t('album.shareAssetCount', { count: formatCount(share.asset_count, 'media') });
}

function shareSearchText(share: ShareLink) {
  const expiry = share.expires_at ? formatDate(share.expires_at) : t('common.never');
  return `${share.title} ${share.token} ${shareScopeLabel(share)} ${shareStatusLabel(share)} ${expiry}`.toLowerCase();
}

function shareMatchesStatus(share: ShareLink) {
  if (shareStatusFilter.value === 'all') return true;
  if (shareStatusFilter.value === 'active') return !share.revoked_at && !isShareExpired(share);
  if (shareStatusFilter.value === 'expired') return !share.revoked_at && isShareExpired(share);
  if (shareStatusFilter.value === 'revoked') return Boolean(share.revoked_at);
  if (shareStatusFilter.value === 'never') return !share.revoked_at && !share.expires_at;
  return !share.revoked_at && isShareExpiringSoon(share);
}

function shareStatusLabel(share: ShareLink) {
  if (share.revoked_at) return t('album.shareRevoked');
  if (isShareExpired(share)) return t('admin.shareStatusExpired');
  if (isShareExpiringSoon(share)) return t('album.shareStatusExpiring');
  if (!share.expires_at) return t('album.shareStatusNever');
  return t('admin.shareStatusActive');
}

function shareStatusClass(share: ShareLink) {
  if (share.revoked_at || isShareExpired(share)) return 'off';
  if (isShareExpiringSoon(share)) return 'active';
  return 'neutral';
}

function isShareExpired(share: ShareLink) {
  if (!share.expires_at) return false;
  const expiresAt = new Date(share.expires_at).getTime();
  return !Number.isNaN(expiresAt) && expiresAt < Date.now();
}

function isShareExpiringSoon(share: ShareLink) {
  if (!share.expires_at) return false;
  const expiresAt = new Date(share.expires_at).getTime();
  if (Number.isNaN(expiresAt)) return false;
  const daysRemaining = (expiresAt - Date.now()) / 86400000;
  return daysRemaining >= 0 && daysRemaining <= 7;
}

async function copyShareLink(share: ShareLink) {
  try {
    await navigator.clipboard?.writeText(`${location.origin}/share/${share.token}`);
    showMessage(t('admin.shareCopied'));
  } catch (err) {
    showMessage(errorMessage(err, t('admin.unableCopyShare')), 'error');
  }
}

function openEditShare(share: ShareLink) {
  editShareTarget.value = share;
  editShareTitle.value = share.title;
  editSharePassword.value = undefined;
  if (share.expires_at) {
    const diff = Math.ceil((new Date(share.expires_at).getTime() - Date.now()) / 86400000);
    editShareExpiry.value = diff > 0 ? diff : 1;
  } else {
    editShareExpiry.value = 0;
  }
}

function closeEditShare() {
  editShareTarget.value = null;
  editShareTitle.value = '';
  editShareExpiry.value = 7;
  editSharePassword.value = undefined;
}

async function confirmEditShare() {
  const share = editShareTarget.value;
  if (!share) return;
  try {
    const payload: { title?: string; expires_in_days?: number; password?: string } = {};
    if (editShareTitle.value !== share.title) payload.title = editShareTitle.value;
    payload.expires_in_days = editShareExpiry.value;
    if (editSharePassword.value !== undefined) {
      payload.password = editSharePassword.value || '';
    }
    const updated = await api.updateAdminShare(share.id, payload);
    const idx = shares.value.findIndex((s) => s.id === share.id);
    if (idx !== -1) shares.value[idx] = updated;
    showMessage(t('album.shareUpdated'));
    closeEditShare();
  } catch (err) {
    showMessage(errorMessage(err, t('album.unableUpdateShare')), 'error');
  }
}

function openDeleteShare(share: ShareLink) {
  deleteShareTarget.value = share;
}

function closeDeleteShare() {
  deleteShareTarget.value = null;
}

async function confirmDeleteShare() {
  const share = deleteShareTarget.value;
  if (!share) return;
  try {
    await api.deleteAdminShare(share.id);
    shares.value = shares.value.filter((s) => s.id !== share.id);
    showMessage(t('album.shareDeleted'));
    closeDeleteShare();
  } catch (err) {
    showMessage(errorMessage(err, t('album.unableDeleteShare')), 'error');
  }
}

function roleLabel(role: User['role']) {
  return role === 'admin' ? t('common.admin') : t('common.member');
}

function jobStatusLabel(status: string) {
  if (status === 'completed') return t('admin.statusFinished');
  if (status === 'failed') return t('admin.statusFailed');
  if (status === 'running') return t('admin.statusRunning');
  if (status === 'queued') return t('admin.statusQueued');
  return status;
}
</script>
