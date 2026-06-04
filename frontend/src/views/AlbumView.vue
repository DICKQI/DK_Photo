<template>
  <main class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-sticky-top">
        <div class="brand-row">
          <div class="brand-mark">DK</div>
          <strong>DK Photo</strong>
        </div>
        <button class="sidebar-action" :class="{ active: !currentFolder && !favoritesView && !allPhotosView && !recentView && !videosView && !placesView && !currentPlace && !currentTag && !currentRating && !currentCamera && !currentLens && !currentAlbum && !albumOverviewView }" @click="goRoot">
          <FolderRoot :size="18" />
          {{ t('album.allLibraries') }}
        </button>
        <button class="sidebar-action" :class="{ active: allPhotosView }" @click="openAllPhotosView">
          <Images :size="18" />
          {{ t('album.allPhotos') }}
        </button>
        <button class="sidebar-action" :class="{ active: recentView }" @click="openRecentView">
          <Clock :size="18" />
          {{ t('album.recentlyAdded') }}
        </button>
        <button class="sidebar-action" :class="{ active: videosView }" @click="openVideosView">
          <Video :size="18" />
          {{ t('album.videos') }}
        </button>
        <button class="sidebar-action" :class="{ active: placesView }" @click="openPlacesView">
          <MapPin :size="18" />
          {{ t('album.places') }}
        </button>
        <button class="sidebar-action" :class="{ active: favoritesView }" @click="openFavoritesView">
          <Star :size="18" />
          {{ t('album.favorites') }}
        </button>
        <button class="sidebar-action" :class="{ active: albumOverviewView }" @click="openAlbumOverviewView">
          <Images :size="18" />
          {{ t('album.albums') }}
        </button>
      </div>

      <div class="sidebar-scroll">
      <label class="library-filter">
        <Search :size="16" />
        <input v-model="libraryFilter" :placeholder="t('album.filterLibraries')" />
        <button v-if="libraryFilter" class="search-clear" type="button" :title="t('album.clearLibraryFilter')" @click="libraryFilter = ''">
          <X :size="14" />
        </button>
      </label>
      <div class="sidebar-meta">
        <span>{{ libraryListSummary }}</span>
        <button v-if="libraryFilter" type="button" @click="libraryFilter = ''">{{ t('common.reset') }}</button>
      </div>
      <div class="tree-scroll">
        <button
          v-for="folder in filteredRootFolders"
          :key="folder.id"
          class="tree-item"
          :class="{ active: currentFolder?.id === folder.id }"
          @click="openFolder(folder)"
        >
          <Folder :size="17" />
          <span>{{ folder.name }}</span>
          <small>{{ folder.photo_count }}</small>
        </button>
        <div v-if="rootFolders.length && !filteredRootFolders.length" class="tree-empty">
          <Search :size="18" />
          <span>{{ t('album.noMatchingLibraries') }}</span>
        </div>
      </div>

      <div class="sidebar-section-header" @click="toggleSection('albums')">
        <span class="section-header-label">
          <ChevronDown :size="14" class="collapse-chevron" :class="{ collapsed: collapsedSections['albums'] }" />
          <span>{{ t('album.albums') }}</span>
        </span>
        <div class="sidebar-section-actions" @click.stop>
          <button type="button" :title="t('album.newAlbum')" @click="openNewAlbumModal">
            <Plus :size="14" />
          </button>
          <button type="button" :title="t('album.refreshAlbums')" @click="loadAlbums">
            <RefreshCw :size="14" />
          </button>
        </div>
      </div>
      <div v-show="!collapsedSections['albums']">
        <div v-if="photoAlbums.length" class="album-filter-row">
          <label class="library-filter album-filter">
            <Search :size="16" />
            <input v-model="albumFilter" :placeholder="t('album.filterAlbums')" />
            <button v-if="albumFilter" class="search-clear" type="button" :title="t('album.clearAlbumFilter')" @click="albumFilter = ''">
              <X :size="14" />
            </button>
          </label>
          <div class="album-sort-controls segmented-control" :aria-label="t('album.sortAlbums')">
            <button :class="{ active: albumSortMode === 'updated' }" :title="t('album.sortAlbumsByUpdated')" @click="setAlbumSortMode('updated')">
              {{ t('common.sortDate') }}
            </button>
            <button :class="{ active: albumSortMode === 'name' }" :title="t('album.sortAlbumsByName')" @click="setAlbumSortMode('name')">
              {{ t('common.sortName') }}
            </button>
            <button :class="{ active: albumSortMode === 'count' }" :title="t('album.sortAlbumsByCount')" @click="setAlbumSortMode('count')">
              {{ t('common.sortSize') }}
            </button>
            <button :class="{ active: albumSortDirection === 'asc' }" :title="albumSortDirectionTitle" @click="toggleAlbumSortDirection">
              <ArrowUpAZ v-if="albumSortDirection === 'asc'" :size="14" />
              <ArrowDownAZ v-else :size="14" />
            </button>
          </div>
        </div>
        <div class="album-list">
          <div v-if="albumsLoading" class="shares-loading">
            <LoaderCircle class="spin" :size="18" />
            <span>{{ t('album.loadingAlbums') }}</span>
          </div>
          <div v-else-if="!photoAlbums.length" class="shares-empty">
            <span>{{ t('album.noAlbums') }}</span>
            <small>{{ t('album.noAlbumsHint') }}</small>
          </div>
          <div v-else-if="!filteredPhotoAlbums.length" class="shares-empty">
            <span>{{ t('album.noMatchingAlbums') }}</span>
            <small>{{ t('album.noAlbumsMatch', { query: albumFilter.trim() }) }}</small>
          </div>
          <template v-else>
            <button
              v-for="album in filteredPhotoAlbums"
              :key="album.id"
              class="tree-item album-tree-item"
              :class="{ active: currentAlbum?.id === album.id }"
              @click="openAlbumView(album)"
            >
              <span class="album-list-cover">
                <img v-if="album.cover_asset_id" :src="thumbnailUrl(album.cover_asset_id, 'small')" alt="" loading="lazy" />
                <Images v-else :size="17" />
              </span>
              <span>{{ album.name }}</span>
              <small>{{ album.asset_count }}</small>
            </button>
          </template>
        </div>
      </div>

      <div class="sidebar-section-header" @click="toggleSection('cameras')">
        <span class="section-header-label">
          <ChevronDown :size="14" class="collapse-chevron" :class="{ collapsed: collapsedSections['cameras'] }" />
          <span>{{ t('album.cameras') }}</span>
        </span>
        <button type="button" :title="t('album.refreshCameras')" @click.stop="loadCameras">
          <RefreshCw :size="14" />
        </button>
      </div>
      <div v-show="!collapsedSections['cameras']" class="camera-list">
        <div v-if="camerasLoading" class="shares-loading">
          <LoaderCircle class="spin" :size="18" />
          <span>{{ t('album.loadingCameras') }}</span>
        </div>
        <div v-else-if="!filteredAssetCameras.length" class="shares-empty">
          <span>{{ t('album.noCameras') }}</span>
          <small>{{ t('album.noCamerasHint') }}</small>
        </div>
        <template v-else>
          <button
            v-for="camera in filteredAssetCameras"
            :key="camera.camera_key"
            class="tree-item camera-tree-item"
            :class="{ active: currentCamera?.camera_key === camera.camera_key }"
            @click="openCameraView(camera)"
          >
            <Camera :size="17" />
            <span>{{ camera.label }}</span>
            <small>{{ camera.asset_count }}</small>
          </button>
        </template>
      </div>

      <div class="sidebar-section-header" @click="toggleSection('lenses')">
        <span class="section-header-label">
          <ChevronDown :size="14" class="collapse-chevron" :class="{ collapsed: collapsedSections['lenses'] }" />
          <span>{{ t('album.lenses') }}</span>
        </span>
        <button type="button" :title="t('album.refreshLenses')" @click.stop="loadLenses">
          <RefreshCw :size="14" />
        </button>
      </div>
      <div v-show="!collapsedSections['lenses']" class="lens-list">
        <div v-if="lensesLoading" class="shares-loading">
          <LoaderCircle class="spin" :size="18" />
          <span>{{ t('album.loadingLenses') }}</span>
        </div>
        <div v-else-if="!filteredAssetLenses.length" class="shares-empty">
          <span>{{ t('album.noLenses') }}</span>
          <small>{{ t('album.noLensesHint') }}</small>
        </div>
        <template v-else>
          <button
            v-for="lens in filteredAssetLenses"
            :key="lens.lens_key"
            class="tree-item lens-tree-item"
            :class="{ active: currentLens?.lens_key === lens.lens_key }"
            @click="openLensView(lens)"
          >
            <Aperture :size="17" />
            <span>{{ lens.label }}</span>
            <small>{{ lens.asset_count }}</small>
          </button>
        </template>
      </div>

      <div class="sidebar-section-header" @click="toggleSection('ratings')">
        <span class="section-header-label">
          <ChevronDown :size="14" class="collapse-chevron" :class="{ collapsed: collapsedSections['ratings'] }" />
          <span>{{ t('album.ratings') }}</span>
        </span>
        <button type="button" :title="t('album.refreshRatings')" @click.stop="loadRatings">
          <RefreshCw :size="14" />
        </button>
      </div>
      <div v-show="!collapsedSections['ratings']" class="rating-list">
        <div v-if="ratingsLoading" class="shares-loading">
          <LoaderCircle class="spin" :size="18" />
          <span>{{ t('album.loadingRatings') }}</span>
        </div>
        <div v-else-if="!filteredAssetRatings.length" class="shares-empty">
          <span>{{ t('album.noRatings') }}</span>
          <small>{{ t('album.noRatingsHint') }}</small>
        </div>
        <template v-else>
          <button
            v-for="rating in filteredAssetRatings"
            :key="rating.rating"
            class="tree-item rating-tree-item"
            :class="{ active: currentRating === rating.rating }"
            @click="openRatingView(rating.rating)"
          >
            <Star :size="17" fill="currentColor" />
            <span>{{ t('album.ratingAtLeast', { rating: rating.rating }) }}</span>
            <small>{{ rating.asset_count }}</small>
          </button>
        </template>
      </div>

      <div class="sidebar-section-header" @click="toggleSection('tags')">
        <span class="section-header-label">
          <ChevronDown :size="14" class="collapse-chevron" :class="{ collapsed: collapsedSections['tags'] }" />
          <span>{{ t('album.tags') }}</span>
        </span>
        <button type="button" :title="t('album.refreshTags')" @click.stop="loadTags">
          <RefreshCw :size="14" />
        </button>
      </div>
      <div v-show="!collapsedSections['tags']">
        <label v-if="assetTags.length" class="library-filter tag-filter">
          <Search :size="16" />
          <input v-model="tagFilter" :placeholder="t('album.searchTags')" />
          <button v-if="tagFilter" class="search-clear" type="button" :title="t('common.clearSearch')" @click="tagFilter = ''">
            <X :size="14" />
          </button>
        </label>
        <div class="tag-list">
          <div v-if="tagsLoading" class="shares-loading">
            <LoaderCircle class="spin" :size="18" />
            <span>{{ t('album.loadingTags') }}</span>
          </div>
          <div v-else-if="!assetTags.length" class="shares-empty">
            <span>{{ t('album.noTags') }}</span>
            <small>{{ t('album.noTagsHint') }}</small>
          </div>
          <div v-else-if="!filteredAssetTags.length" class="shares-empty">
            <span>{{ t('album.noMatchingTags') }}</span>
            <small>{{ t('album.noTagsMatch', { query: tagFilter.trim() }) }}</small>
          </div>
          <template v-else>
            <div
              v-for="tag in filteredAssetTags"
              :key="tag.name"
              class="tag-tree-row"
              :class="{ active: currentTag === tag.name }"
            >
              <button class="tree-item tag-tree-item" @click="openTagView(tag.name)">
                <Tag :size="17" />
                <span>{{ tag.name }}</span>
                <small>{{ tag.asset_count }}</small>
              </button>
              <div class="tag-row-actions">
                <button type="button" :title="t('album.renameTag')" @click="openRenameTag(tag)">
                  <Pencil :size="14" />
                </button>
                <button type="button" :title="t('album.deleteTag')" @click="openDeleteTag(tag)">
                  <Trash2 :size="14" />
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>

      <button class="sidebar-action" :class="{ active: showSharesPanel }" @click="toggleSharesPanel">
        <Share2 :size="18" />
        {{ t('album.myShareLinks') }}
      </button>
      <div v-if="showSharesPanel" class="shares-panel">
        <div v-if="sharesLoading" class="shares-loading">
          <LoaderCircle class="spin" :size="18" />
          <span>{{ t('album.loadingPhotos') }}</span>
        </div>
        <div v-else-if="!myShares.length" class="shares-empty">
          <span>{{ t('album.noShareLinks') }}</span>
          <small>{{ t('album.noShareLinksHint') }}</small>
        </div>
        <template v-else>
          <label class="library-filter share-filter">
            <Search :size="16" />
            <input v-model="shareFilter" :placeholder="t('album.filterShareLinks')" />
            <button v-if="shareFilter" class="search-clear" type="button" :title="t('album.clearShareFilter')" @click="shareFilter = ''">
              <X :size="14" />
            </button>
          </label>
          <div class="share-status-filter segmented-control" :aria-label="t('album.filterShareStatus')">
            <button :class="{ active: shareStatusFilter === 'all' }" @click="shareStatusFilter = 'all'">{{ t('album.shareStatusAll') }}</button>
            <button :class="{ active: shareStatusFilter === 'active' }" @click="shareStatusFilter = 'active'">{{ t('admin.shareStatusActive') }}</button>
            <button :class="{ active: shareStatusFilter === 'expiring' }" @click="shareStatusFilter = 'expiring'">{{ t('album.shareStatusExpiring') }}</button>
            <button :class="{ active: shareStatusFilter === 'expired' }" @click="shareStatusFilter = 'expired'">{{ t('admin.shareStatusExpired') }}</button>
            <button :class="{ active: shareStatusFilter === 'never' }" @click="shareStatusFilter = 'never'">{{ t('album.shareStatusNever') }}</button>
          </div>
          <div v-if="!filteredMyShares.length" class="shares-empty">
            <span>{{ t('album.noMatchingShares') }}</span>
            <small>{{ shareEmptyHint }}</small>
          </div>
          <div v-else class="shares-list">
            <div v-for="share in filteredMyShares" :key="share.id" class="share-item">
              <div class="share-item-info">
                <span class="share-item-title">{{ share.title }}</span>
                <span class="share-item-meta">{{ shareScopeLabel(share) }}</span>
                <span class="share-item-meta share-item-status">
                  <small class="status-pill share-status-pill" :class="shareStatusClass(share)">{{ shareStatusLabel(share) }}</small>
                  <span class="share-item-expiry">{{ shareExpiryLabel(share) }}</span>
                </span>
              </div>
              <div class="share-item-actions">
                <button class="share-item-btn" :title="t('album.shareCopyLink')" @click="copyMyShareLink(share)">
                  <Link2 :size="15" />
                </button>
                <button class="share-item-btn" :title="t('common.edit')" @click="openEditShare(share)">
                  <Pencil :size="15" />
                </button>
                <button class="share-item-btn" :title="t('common.delete')" @click="openDeleteShare(share)">
                  <Trash2 :size="15" />
                </button>
              </div>
            </div>
          </div>
        </template>
      </div>
      </div>

      <div class="sidebar-bottom-fixed">
        <RouterLink v-if="user?.role === 'admin'" class="admin-link" to="/admin">
          <Settings :size="18" />
          {{ t('common.management') }}
        </RouterLink>
      </div>
    </aside>

    <section class="content-pane">
      <header class="topbar">
        <button class="icon-button mobile-only" @click="mobileTree = !mobileTree" :title="t('album.foldersTitle')">
          <PanelLeft :size="19" />
        </button>
        <nav class="breadcrumbs">
          <button @click="goRoot">{{ t('album.breadcrumbLibraries') }}</button>
          <template v-if="albumOverviewView || currentAlbum">
            <ChevronRight :size="15" />
            <button v-if="currentAlbum" @click="openAlbumOverviewView">{{ t('album.albums') }}</button>
            <span v-else>{{ t('album.albums') }}</span>
          </template>
          <template v-if="currentAlbum">
            <ChevronRight :size="15" />
            <span>{{ currentAlbum.name }}</span>
          </template>
          <template v-if="allPhotosView">
            <ChevronRight :size="15" />
            <span>{{ t('album.allPhotos') }}</span>
          </template>
          <template v-if="recentView">
            <ChevronRight :size="15" />
            <span>{{ t('album.recentlyAdded') }}</span>
          </template>
          <template v-if="videosView">
            <ChevronRight :size="15" />
            <span>{{ t('album.videos') }}</span>
          </template>
          <template v-if="placesView">
            <ChevronRight :size="15" />
            <button v-if="currentPlace" @click="openPlacesView">{{ t('album.places') }}</button>
            <span v-else>{{ t('album.places') }}</span>
          </template>
          <template v-if="currentPlace">
            <ChevronRight :size="15" />
            <span>{{ currentPlace.label }}</span>
          </template>
          <template v-if="currentTag">
            <ChevronRight :size="15" />
            <span>{{ currentTag }}</span>
          </template>
          <template v-if="currentRating">
            <ChevronRight :size="15" />
            <span>{{ t('album.ratingAtLeast', { rating: currentRating }) }}</span>
          </template>
          <template v-if="currentCamera">
            <ChevronRight :size="15" />
            <span>{{ currentCamera.label }}</span>
          </template>
          <template v-if="currentLens">
            <ChevronRight :size="15" />
            <span>{{ currentLens.label }}</span>
          </template>
          <template v-if="favoritesView">
            <ChevronRight :size="15" />
            <span>{{ t('album.favorites') }}</span>
          </template>
          <template v-for="ancestor in currentFolder?.ancestors || []" :key="ancestor.id">
            <ChevronRight :size="15" />
            <button @click="openFolder(ancestor)">{{ ancestor.name }}</button>
          </template>
          <template v-if="currentFolder">
            <ChevronRight :size="15" />
            <span>{{ currentFolder.name }}</span>
          </template>
        </nav>
        <div class="topbar-actions">
          <button
            v-if="assetActionsEnabled"
            class="icon-button"
            :class="{ active: selectionMode }"
            :title="selectionMode ? t('album.cancelSelection') : t('album.selectPhotos')"
            @click="toggleSelectionMode"
          >
            <ListChecks :size="18" />
          </button>
          <button
            v-if="currentFolder"
            class="icon-button"
            :title="t('album.shareCurrentFolder')"
            @click="shareCurrentFolder"
          >
            <Share2 :size="18" />
          </button>
          <button
            v-if="currentAlbum"
            class="icon-button"
            :title="t('album.addMediaToAlbum')"
            @click="openAlbumAssetPicker"
          >
            <Plus :size="18" />
          </button>
          <button
            v-if="currentAlbum"
            class="icon-button"
            :disabled="sharingAlbum"
            :title="t('album.shareCurrentAlbum')"
            @click="shareCurrentAlbum"
          >
            <LoaderCircle v-if="sharingAlbum" class="spin" :size="18" />
            <Share2 v-else :size="18" />
          </button>
          <button
            v-if="currentAlbum"
            class="icon-button"
            :title="t('album.editAlbum')"
            @click="openEditAlbum"
          >
            <Pencil :size="18" />
          </button>
          <button
            v-if="currentAlbum"
            class="icon-button danger-icon-button"
            :title="t('album.deleteAlbum')"
            @click="openDeleteAlbum"
          >
            <Trash2 :size="18" />
          </button>
          <button
            v-if="currentFolder"
            class="icon-button"
            :class="{ active: favoriteFilter, 'favorite-filter-button': favoriteFilter }"
            :title="favoriteFilter ? t('album.showAllPhotos') : t('album.showFavoritesOnly')"
            @click="toggleFavoriteFilter"
          >
            <Star :size="18" />
          </button>
          <button
            v-if="currentFolder"
            class="icon-button"
            :class="{ active: includeSubfolders }"
            :title="includeSubfolders ? t('album.showCurrentFolderOnly') : t('album.includeSubfolderPhotos')"
            @click="toggleIncludeSubfolders"
          >
            <FolderTree :size="18" />
          </button>
          <button
            v-if="albumOverviewView"
            class="icon-button"
            :title="t('album.newAlbum')"
            @click="openNewAlbumModal"
          >
            <Plus :size="18" />
          </button>
          <button
            v-if="albumOverviewView"
            class="icon-button"
            :disabled="albumsLoading"
            :title="t('album.refreshAlbums')"
            @click="loadAlbums"
          >
            <LoaderCircle v-if="albumsLoading" class="spin" :size="18" />
            <RefreshCw v-else :size="18" />
          </button>
          <label v-if="albumOverviewView && photoAlbums.length" class="search-box album-overview-search" :class="{ searching: albumsLoading }">
            <LoaderCircle v-if="albumsLoading" class="spin" :size="17" />
            <Search v-else :size="17" />
            <input
              v-model="albumFilter"
              :disabled="loading"
              :placeholder="t('album.filterAlbums')"
            />
            <button v-if="albumFilter" class="search-clear" type="button" :title="t('album.clearAlbumFilter')" @click="albumFilter = ''">
              <X :size="15" />
            </button>
          </label>
          <div v-if="albumOverviewView && photoAlbums.length" class="segmented-control album-overview-sort" :aria-label="t('album.sortAlbums')">
            <button :class="{ active: albumSortMode === 'updated' }" :title="t('album.sortAlbumsByUpdated')" @click="setAlbumSortMode('updated')">
              <Clock :size="16" />
              {{ t('common.sortDate') }}
            </button>
            <button :class="{ active: albumSortMode === 'name' }" :title="t('album.sortAlbumsByName')" @click="setAlbumSortMode('name')">
              <ArrowDownAZ :size="16" />
              {{ t('common.sortName') }}
            </button>
            <button :class="{ active: albumSortMode === 'count' }" :title="t('album.sortAlbumsByCount')" @click="setAlbumSortMode('count')">
              <Images :size="16" />
              {{ t('common.sortSize') }}
            </button>
            <button :class="{ active: albumSortDirection === 'asc' }" :title="albumSortDirectionTitle" @click="toggleAlbumSortDirection">
              <ArrowUpAZ v-if="albumSortDirection === 'asc'" :size="16" />
              <ArrowDownAZ v-else :size="16" />
              {{ albumSortDirection === 'asc' ? t('common.sortAsc') : t('common.sortDesc') }}
            </button>
          </div>
          <label v-if="!albumOverviewView" class="search-box" :class="{ searching: searchLoading }">
            <LoaderCircle v-if="searchLoading" class="spin" :size="17" />
            <Search v-else :size="17" />
            <input
              v-model="search"
              :disabled="loading"
              :placeholder="searchPlaceholder"
              @input="queueAssetSearch"
            />
            <button v-if="search" class="search-clear" type="button" :title="t('common.clearSearch')" @click="clearSearch">
              <X :size="15" />
            </button>
          </label>
          <button
            v-if="!albumOverviewView && hasActiveAssetFilters"
            class="icon-button"
            :title="t('album.clearAssetFilters')"
            @click="clearAssetFilters"
          >
            <FilterX :size="18" />
          </button>
          <div v-if="!albumOverviewView" class="segmented-control" :aria-label="t('album.mediaFilter')">
            <button :class="{ active: activeMediaFilter === 'all' }" :title="t('album.showAllMedia')" @click="setMediaFilter('all')">
              <Images :size="16" />
              {{ t('common.all') }}
            </button>
            <button :class="{ active: activeMediaFilter === 'image' }" :title="t('album.showImagesOnly')" @click="setMediaFilter('image')">
              <Images :size="16" />
              {{ t('common.photos') }}
            </button>
            <button :class="{ active: activeMediaFilter === 'video' }" :title="t('album.showVideosOnly')" @click="setMediaFilter('video')">
              <Video :size="16" />
              {{ t('common.videos') }}
            </button>
          </div>
          <label v-if="!albumOverviewView" class="rating-filter" :title="t('album.ratingFilter')">
            <Star :size="16" />
            <select v-model.number="ratingFilter" @change="setRatingFilter(ratingFilter)">
              <option :value="0">{{ t('album.allRatings') }}</option>
              <option v-for="rating in ratingOptions" :key="rating" :value="rating">
                {{ t('album.ratingAtLeast', { rating }) }}
              </option>
            </select>
          </label>
          <div v-if="!albumOverviewView" class="segmented-control sort-control" :aria-label="t('album.sortPhotos')">
            <button :class="{ active: sortMode === 'date' }" :title="t('album.sortByDate')" @click="setSortMode('date')">
              <Clock :size="16" />
              {{ t('common.sortDate') }}
            </button>
            <button :class="{ active: sortMode === 'name' }" :title="t('album.sortByName')" @click="setSortMode('name')">
              <ArrowDownAZ :size="16" />
              {{ t('common.sortName') }}
            </button>
            <button :class="{ active: sortMode === 'size' }" :title="t('album.sortBySize')" @click="setSortMode('size')">
              <HardDrive :size="16" />
              {{ t('common.sortSize') }}
            </button>
            <button :class="{ active: sortDirection === 'asc' }" :title="sortDirectionTitle" @click="toggleSortDirection">
              <ArrowUpAZ v-if="sortDirection === 'asc'" :size="16" />
              <ArrowDownAZ v-else :size="16" />
              {{ sortDirection === 'asc' ? t('common.sortAsc') : t('common.sortDesc') }}
            </button>
          </div>
          <div v-if="!albumOverviewView" class="segmented-control" :aria-label="t('album.thumbnailSize')">
            <button :class="{ active: thumbSize === 'small' }" :title="t('album.compactThumbnails')" @click="setThumbSize('small')">
              <Grid2X2 :size="16" />
              {{ t('common.compact') }}
            </button>
            <button :class="{ active: thumbSize === 'medium' }" :title="t('album.balancedThumbnails')" @click="setThumbSize('medium')">
              <LayoutGrid :size="16" />
              {{ t('common.balanced') }}
            </button>
            <button :class="{ active: thumbSize === 'large' }" :title="t('album.largeThumbnails')" @click="setThumbSize('large')">
              <Maximize2 :size="16" />
              {{ t('common.large') }}
            </button>
          </div>
          <LanguageToggle />
          <button class="icon-button" :title="t('common.toggleTheme')" @click="toggleTheme">
            <Sun v-if="isDark" :size="18" />
            <Moon v-else :size="18" />
          </button>
          <button class="icon-button" :title="t('common.signOut')" @click="logout">
            <LogOut :size="18" />
          </button>
        </div>
      </header>

      <div v-if="mobileTree" class="mobile-folder-sheet">
        <div class="mobile-sheet-header">
          <strong>{{ t('common.libraries') }}</strong>
          <button class="icon-button" :title="t('album.closeFolders')" @click="mobileTree = false">
            <X :size="17" />
          </button>
        </div>
        <label class="library-filter mobile-library-filter">
          <Search :size="16" />
          <input v-model="libraryFilter" :placeholder="t('album.filterLibraries')" />
          <button v-if="libraryFilter" class="search-clear" type="button" :title="t('album.clearLibraryFilter')" @click="libraryFilter = ''">
            <X :size="14" />
          </button>
        </label>
        <label v-if="photoAlbums.length" class="library-filter mobile-library-filter">
          <Search :size="16" />
          <input v-model="albumFilter" :placeholder="t('album.filterAlbums')" />
          <button v-if="albumFilter" class="search-clear" type="button" :title="t('album.clearAlbumFilter')" @click="albumFilter = ''">
            <X :size="14" />
          </button>
        </label>
        <button class="mobile-folder-button" :class="{ active: !currentFolder && !favoritesView && !allPhotosView && !recentView && !videosView && !placesView && !currentPlace && !currentTag && !currentRating && !currentCamera && !currentLens && !currentAlbum && !albumOverviewView }" @click="goRoot">
          <FolderRoot :size="17" />
          <span>{{ t('album.allLibraries') }}</span>
          <small>{{ rootFolders.length }}</small>
        </button>
        <button class="mobile-folder-button" :class="{ active: allPhotosView }" @click="openAllPhotosView">
          <Images :size="17" />
          <span>{{ t('album.allPhotos') }}</span>
          <small>{{ assets.length }}</small>
        </button>
        <button class="mobile-folder-button" :class="{ active: recentView }" @click="openRecentView">
          <Clock :size="17" />
          <span>{{ t('album.recentlyAdded') }}</span>
          <small>{{ assets.length }}</small>
        </button>
        <button class="mobile-folder-button" :class="{ active: videosView }" @click="openVideosView">
          <Video :size="17" />
          <span>{{ t('album.videos') }}</span>
          <small>{{ assets.length }}</small>
        </button>
        <button class="mobile-folder-button" :class="{ active: placesView }" @click="openPlacesView">
          <MapPin :size="17" />
          <span>{{ t('album.places') }}</span>
          <small>{{ assets.length }}</small>
        </button>
        <button class="mobile-folder-button" :class="{ active: favoritesView }" @click="openFavoritesView">
          <Star :size="17" />
          <span>{{ t('album.favorites') }}</span>
          <small>{{ assets.length }}</small>
        </button>
        <button class="mobile-folder-button" :class="{ active: albumOverviewView }" @click="openAlbumOverviewView">
          <Images :size="17" />
          <span>{{ t('album.albums') }}</span>
          <small>{{ photoAlbums.length }}</small>
        </button>
        <button
          v-for="camera in filteredAssetCameras"
          :key="`camera-${camera.camera_key}`"
          class="mobile-folder-button"
          :class="{ active: currentCamera?.camera_key === camera.camera_key }"
          @click="openCameraView(camera)"
        >
          <Camera :size="17" />
          <span>{{ camera.label }}</span>
          <small>{{ camera.asset_count }}</small>
        </button>
        <button
          v-for="lens in filteredAssetLenses"
          :key="`lens-${lens.lens_key}`"
          class="mobile-folder-button"
          :class="{ active: currentLens?.lens_key === lens.lens_key }"
          @click="openLensView(lens)"
        >
          <Aperture :size="17" />
          <span>{{ lens.label }}</span>
          <small>{{ lens.asset_count }}</small>
        </button>
        <button
          v-for="rating in filteredAssetRatings"
          :key="`rating-${rating.rating}`"
          class="mobile-folder-button"
          :class="{ active: currentRating === rating.rating }"
          @click="openRatingView(rating.rating)"
        >
          <Star :size="17" fill="currentColor" />
          <span>{{ t('album.ratingAtLeast', { rating: rating.rating }) }}</span>
          <small>{{ rating.asset_count }}</small>
        </button>
        <label v-if="assetTags.length" class="library-filter mobile-library-filter">
          <Search :size="16" />
          <input v-model="tagFilter" :placeholder="t('album.searchTags')" />
          <button v-if="tagFilter" class="search-clear" type="button" :title="t('common.clearSearch')" @click="tagFilter = ''">
            <X :size="14" />
          </button>
        </label>
        <button
          v-for="tag in filteredAssetTags"
          :key="`tag-${tag.name}`"
          class="mobile-folder-button"
          :class="{ active: currentTag === tag.name }"
          @click="openTagView(tag.name)"
        >
          <Tag :size="17" />
          <span>{{ tag.name }}</span>
          <small>{{ tag.asset_count }}</small>
        </button>
        <button
          v-for="album in filteredPhotoAlbums"
          :key="`album-${album.id}`"
          class="mobile-folder-button"
          :class="{ active: currentAlbum?.id === album.id }"
          @click="openAlbumView(album)"
        >
          <Images :size="17" />
          <span>{{ album.name }}</span>
          <small>{{ album.asset_count }}</small>
        </button>
        <button
          v-for="folder in filteredRootFolders"
          :key="folder.id"
          class="mobile-folder-button"
          :class="{ active: currentFolder?.id === folder.id }"
          @click="openFolder(folder)"
        >
          <Folder :size="17" />
          <span>{{ folder.name }}</span>
          <small>{{ folder.photo_count }}</small>
        </button>
        <div v-if="!rootFolders.length" class="mobile-sheet-empty">
          {{ t('album.noLibrariesAvailable') }}
        </div>
        <div v-if="photoAlbums.length && albumFilter.trim() && !filteredPhotoAlbums.length" class="mobile-sheet-empty">
          {{ t('album.noAlbumsMatch', { query: albumFilter.trim() }) }}
        </div>
        <div v-if="assetTags.length && tagFilter.trim() && !filteredAssetTags.length" class="mobile-sheet-empty">
          {{ t('album.noTagsMatch', { query: tagFilter.trim() }) }}
        </div>
        <div v-if="rootFolders.length && libraryFilter.trim() && !filteredRootFolders.length" class="mobile-sheet-empty">
          {{ t('album.noLibrariesMatch', { query: libraryFilter.trim() }) }}
        </div>
      </div>

      <section class="library-status" :class="{ 'album-status': currentAlbum }">
        <div v-if="currentAlbum" class="album-status-main">
          <div class="album-status-cover" :aria-label="t('album.albumCover')">
            <img v-if="currentAlbum.cover_asset_id" :src="thumbnailUrl(currentAlbum.cover_asset_id, 'small')" alt="" loading="lazy" />
            <Images v-else :size="34" />
          </div>
          <div class="album-status-copy">
            <p class="eyebrow">{{ pageEyebrow }}</p>
            <h1>{{ pageTitle }}</h1>
            <p class="album-status-description" :class="{ empty: !hasAlbumDescription }">{{ albumDescriptionText }}</p>
            <div class="album-status-meta">
              <span>{{ t('album.updatedAt', { date: albumUpdatedLabel }) }}</span>
              <span>{{ t('album.createdAt', { date: albumCreatedLabel }) }}</span>
            </div>
          </div>
        </div>
        <div v-else>
          <p class="eyebrow">{{ pageEyebrow }}</p>
          <h1>{{ pageTitle }}</h1>
        </div>
        <div class="status-metrics">
          <span v-if="albumOverviewView">
            <Images :size="16" />
            {{ t('album.albumCount', { count: formatCount(filteredPhotoAlbums.length, 'album') }) }}
          </span>
          <span v-if="albumOverviewView">
            <Grid2X2 :size="16" />
            {{ t('album.albumMediaTotal', { count: formatCount(albumOverviewMediaCount, 'media') }) }}
          </span>
          <span v-if="!albumOverviewView">
            <Folder :size="16" />
            {{ formatCount(visibleChildFolders.length, 'folder') }}
          </span>
          <span v-if="!albumOverviewView">
            <Images :size="16" />
            {{ formatCount(visibleMediaCount, 'media') }}
          </span>
          <span v-if="placeOverviewActive">
            <MapPin :size="16" />
            {{ t('album.placeClusterCount', { count: displayedPlaceClusters.length }) }}
          </span>
          <span v-if="includeSubfolders && currentFolder">
            <FolderTree :size="16" />
            {{ t('album.subfolderPhotosIncluded') }}
          </span>
        </div>
      </section>

      <section v-if="loading" class="empty-state">
        <div class="skeleton-grid" :aria-label="t('album.loadingPhotos')">
          <span v-for="item in 8" :key="item" class="skeleton-card"></span>
        </div>
      </section>

      <section v-else-if="error" class="empty-state">
        <ImageOff :size="34" />
        <strong>{{ error }}</strong>
        <button class="secondary-button" @click="retryCurrentView">
          <RefreshCw :size="17" />
          {{ t('common.tryAgain') }}
        </button>
      </section>

      <section v-else-if="albumOverviewView" class="album-overview">
        <div v-if="!photoAlbums.length" class="album-overview-empty">
          <Images :size="36" />
          <strong>{{ t('album.noAlbums') }}</strong>
          <span>{{ t('album.noAlbumsHint') }}</span>
          <button class="primary-button" @click="openNewAlbumModal">
            <Plus :size="17" />
            {{ t('album.newAlbum') }}
          </button>
        </div>
        <div v-else-if="!filteredPhotoAlbums.length" class="album-overview-empty">
          <Search :size="36" />
          <strong>{{ t('album.noMatchingAlbums') }}</strong>
          <span>{{ t('album.noAlbumsMatch', { query: albumFilter.trim() }) }}</span>
          <button class="secondary-button" @click="albumFilter = ''">
            <X :size="17" />
            {{ t('album.clearAlbumFilter') }}
          </button>
        </div>
        <div v-else class="album-overview-grid">
          <button
            v-for="(album, albumIndex) in filteredPhotoAlbums"
            :key="album.id"
            class="album-card"
            :style="{ '--tile-index': albumIndex }"
            @click="openAlbumView(album)"
          >
            <div class="album-card-cover">
              <img v-if="album.cover_asset_id" :src="thumbnailUrl(album.cover_asset_id, 'small')" alt="" loading="lazy" />
              <Images v-else :size="38" />
              <span class="album-card-count-badge">{{ formatCount(album.asset_count, 'media') }}</span>
            </div>
            <span class="album-card-body">
              <strong class="album-card-name">{{ album.name }}</strong>
              <span class="album-card-desc" :class="{ empty: !album.description }">{{ album.description || t('album.noAlbumDescription') }}</span>
              <span class="album-card-meta">
                {{ t('album.updatedAt', { date: albumUpdatedDateLabel(album) }) }}
              </span>
            </span>
          </button>
        </div>
      </section>

      <section v-else-if="!visibleChildFolders.length && !hasVisibleContent" class="empty-state" :class="{ 'search-empty': hasSearch }">
        <Search v-if="hasSearch" :size="34" />
        <Star v-else-if="favoritesOnlyActive" :size="34" />
        <Images v-else-if="albumOverviewView" :size="34" />
        <MapPin v-else-if="placesView" :size="34" />
        <Tag v-else-if="currentTag" :size="34" />
        <Star v-else-if="currentRating" :size="34" />
        <Camera v-else-if="currentCamera" :size="34" />
        <Aperture v-else-if="currentLens" :size="34" />
        <ImageOff v-else :size="34" />
        <strong>{{ emptyStateTitle }}</strong>
        <span v-if="hasSearch">{{ searchEmptyHint }}</span>
        <span v-else-if="favoritesOnlyActive">{{ favoriteEmptyHint }}</span>
        <span v-else-if="albumOverviewView">{{ t('album.noAlbumsHint') }}</span>
        <span v-else-if="placesView">{{ t('album.noLocationPhotosHint') }}</span>
        <span v-else-if="currentTag">{{ t('album.noTaggedPhotosHint') }}</span>
        <span v-else-if="currentRating">{{ t('album.noRatedPhotosHint') }}</span>
        <span v-else-if="currentCamera">{{ t('album.noCameraPhotosHint') }}</span>
        <span v-else-if="currentLens">{{ t('album.noLensPhotosHint') }}</span>
        <span v-else-if="currentAlbum">{{ t('album.emptyAlbumHint') }}</span>
        <span v-else>{{ t('album.emptyHint') }}</span>
        <button v-if="currentAlbum && !hasSearch" class="primary-button" @click="openAlbumAssetPicker">
          <Plus :size="17" />
          {{ t('album.addMediaToAlbum') }}
        </button>
        <button v-if="hasSearch" class="secondary-button" @click="clearSearch">
          <X :size="17" />
          {{ t('common.clearSearch') }}
        </button>
      </section>

      <section v-else class="grid-wrap" :style="{ '--tile-size': tileSize }">
        <template v-if="placeOverviewActive">
          <article
            v-for="(place, placeIndex) in displayedPlaceClusters"
            :key="`place-${place.key}`"
            class="place-card"
            :style="{ '--tile-index': placeIndex }"
          >
            <button class="place-open" @click="openPlace(place)">
              <span class="place-cover">
                <img v-if="place.coverAssetId" :src="thumbnailUrl(place.coverAssetId, 'small')" alt="" loading="lazy" />
                <MapPin v-else :size="42" />
              </span>
              <span class="place-card-body">
                <strong>{{ place.label }}</strong>
                <span>{{ formatCount(place.assetCount, 'media') }}</span>
                <small>{{ t('album.placeCoordinates', { coordinates: placeCoordinateLabel(place) }) }}</small>
              </span>
            </button>
            <a
              class="place-map-link"
              :href="placeMapUrl(place)"
              target="_blank"
              rel="noreferrer"
              :title="t('viewer.openMap')"
              @click.stop
            >
              <MapPin :size="15" />
              {{ t('viewer.openMap') }}
            </a>
          </article>
        </template>

        <button
          v-for="(folder, folderIndex) in visibleChildFolders"
          :key="folder.id"
          class="folder-card"
          :style="{ '--tile-index': folderIndex }"
          @click="openFolder(folder)"
          @contextmenu.prevent="openContextMenu($event, folder)"
        >
          <div class="folder-cover">
            <img v-if="folder.cover_asset_id" :src="thumbnailUrl(folder.cover_asset_id, 'small')" alt="" loading="lazy" />
            <Folder :size="42" v-else />
          </div>
          <strong>{{ folder.name }}</strong>
          <span>{{ t('album.folderCardMeta', { media: formatCount(folder.photo_count, 'media'), folders: formatCount(folder.folder_count, 'folder') }) }}</span>
        </button>

        <article
          v-for="(asset, index) in displayAssets"
          :key="asset.id"
          class="photo-tile"
          :class="{ selected: selectedAssetIds.has(asset.id) }"
          :style="{ '--tile-index': visibleChildFolders.length + index }"
        >
          <template v-if="selectionMode">
            <button class="photo-select-overlay" @click="toggleAssetSelection(asset.id, index, $event)">
              <span class="photo-thumb">
                <img :src="thumbnailUrl(asset.id, thumbSize)" :alt="asset.filename" loading="lazy" />
                <span v-if="isVideoAsset(asset)" class="photo-media-badge" :title="t('album.videoAsset')">
                  <Play :size="14" fill="currentColor" />
                </span>
                <span class="photo-select-check" :class="{ checked: selectedAssetIds.has(asset.id) }">
                  <Check v-if="selectedAssetIds.has(asset.id)" :size="18" />
                </span>
                <span v-if="asset.rating > 0" class="photo-rating-badge" :title="ratingLabel(asset.rating)">
                  <Star :size="13" fill="currentColor" />
                  {{ asset.rating }}
                </span>
              </span>
              <span class="photo-name">{{ asset.filename }}</span>
              <span class="photo-tags" :title="asset.tags.length ? asset.tags.join(', ') : undefined">
                <span v-for="tag in visibleAssetTags(asset)" :key="tag">{{ tag }}</span>
                <small v-if="asset.tags.length > 3">+{{ asset.tags.length - 3 }}</small>
              </span>
              <span class="photo-meta">
                <span>{{ assetDateLabel(asset) }}</span>
                <span>{{ formatBytes(asset.size) }}</span>
              </span>
            </button>
          </template>
          <template v-else>
            <button class="photo-open" @click="openViewer(index)">
              <span class="photo-thumb">
                <img :src="thumbnailUrl(asset.id, thumbSize)" :alt="asset.filename" loading="lazy" />
                <span v-if="isVideoAsset(asset)" class="photo-media-badge" :title="t('album.videoAsset')">
                  <Play :size="14" fill="currentColor" />
                </span>
                <span class="photo-hover">
                  <Maximize2 :size="17" />
                  {{ t('common.open') }}
                </span>
                <span v-if="asset.rating > 0" class="photo-rating-badge" :title="ratingLabel(asset.rating)">
                  <Star :size="13" fill="currentColor" />
                  {{ asset.rating }}
                </span>
              </span>
              <span class="photo-name">{{ asset.filename }}</span>
              <span class="photo-tags" :title="asset.tags.length ? asset.tags.join(', ') : undefined">
                <span v-for="tag in visibleAssetTags(asset)" :key="tag">{{ tag }}</span>
                <small v-if="asset.tags.length > 3">+{{ asset.tags.length - 3 }}</small>
              </span>
              <span class="photo-meta">
                <span>{{ assetDateLabel(asset) }}</span>
                <span>{{ formatBytes(asset.size) }}</span>
              </span>
            </button>
            <button
              class="photo-favorite-action"
              :class="{ active: asset.is_favorite }"
              :title="asset.is_favorite ? t('album.removeFavorite') : t('album.addFavorite')"
              @click.stop="toggleAssetFavorite(asset)"
            >
              <Star :size="17" />
            </button>
            <button
              v-if="currentAlbum"
              class="photo-cover-action"
              :class="{ active: currentAlbum.cover_asset_id === asset.id }"
              :title="t('album.setAlbumCover')"
              @click.stop="setAlbumCover(asset)"
            >
              <Images :size="17" />
            </button>
            <button class="photo-quick-action" :title="t('album.copyShareLink')" @click="shareAsset(asset)">
              <Share2 :size="17" />
            </button>
          </template>
          <div v-if="showAssetSource && assetSourceLabel(asset)" class="photo-source">
            <span :title="assetSourceLabel(asset)">
              <FolderTree :size="14" />
              {{ assetSourceLabel(asset) }}
            </span>
            <button
              class="photo-source-button"
              :title="t('album.openContainingFolder')"
              :aria-label="t('album.openContainingFolder')"
              @click.stop="openAssetFolder(asset)"
            >
              <FolderOpen :size="15" />
            </button>
          </div>
        </article>
      </section>
      <button
        v-if="canLoadMoreAssets"
        class="load-more-btn"
        @click="loadMoreAssets"
      >
        {{ t('album.loadMore') }}
      </button>
      <button
        v-if="loadingMore && !albumOverviewView"
        class="load-more-btn load-more-btn--loading"
        disabled
      >
        <LoaderCircle class="spin" :size="16" />
        {{ t('album.loadingPhotos') }}
      </button>
    </section>

    <Teleport to="body">
      <PhotoViewer
        v-if="viewerIndex !== null"
        :assets="displayAssets"
        :index="viewerIndex"
        @close="viewerIndex = null"
        @update:index="viewerIndex = $event"
        @share="shareAsset"
        @favorite="toggleAssetFavorite"
        @locate="openAssetFolder"
        :can-add-to-album="true"
        :can-edit-tags="true"
        :can-edit-metadata="true"
        :can-set-album-cover="!!currentAlbum"
        :can-remove-from-album="!!currentAlbum"
        :album-cover-asset-id="currentAlbum?.cover_asset_id ?? null"
        :album-action-busy="removingFromAlbum"
        :shortcuts-disabled="viewerShortcutsDisabled"
        @add-to-album="openCreateAlbumForAsset"
        @update-tags="updateAssetTags"
        @update-metadata="updateAssetMetadata"
        @set-album-cover="setAlbumCover"
        @remove-from-album="removeAssetFromAlbum"
        @downloaded="showToast(t('viewer.downloadStarted'))"
        @download-error="showToast($event)"
      />
    </Teleport>
    <p v-if="toastMessage" class="toast">{{ toastMessage }}</p>

    <Teleport to="body">
      <div v-if="selectionMode" class="selection-action-bar">
        <span class="selection-count">
          <Check :size="18" />
          {{ selectedCountLabel }}
        </span>
        <div class="selection-actions">
          <button class="secondary-button" :disabled="allVisibleAssetsSelected" @click="selectAllVisibleAssets">
            <ListChecks :size="17" />
            {{ t('album.selectAllPhotos') }}
          </button>
          <button class="secondary-button" @click="clearSelection">
            <X :size="17" />
            {{ t('album.clearSelected') }}
          </button>
          <button class="secondary-button" :disabled="selectedAssetIds.size === 0 || downloadingSelection" @click="downloadSelectedAssets">
            <LoaderCircle v-if="downloadingSelection" class="spin" :size="17" />
            <Download v-else :size="17" />
            {{ downloadingSelection ? t('album.downloadingSelected') : t('album.downloadSelected') }}
          </button>
          <button class="secondary-button" :disabled="selectedAssetIds.size === 0 || updatingSelectionFavorite" @click="toggleSelectedFavorites">
            <LoaderCircle v-if="updatingSelectionFavorite" class="spin" :size="17" />
            <Star v-else :size="17" />
            {{ updatingSelectionFavorite ? t('album.updatingFavorites') : selectedFavoriteActionLabel }}
          </button>
          <button class="secondary-button" :disabled="selectedAssetIds.size === 0 || addingSelectionTags" @click="openBulkTagModal">
            <LoaderCircle v-if="addingSelectionTags" class="spin" :size="17" />
            <Tag v-else :size="17" />
            {{ addingSelectionTags ? t('album.addingTagsToSelection') : t('album.addTagsToSelection') }}
          </button>
          <button class="secondary-button" :disabled="selectedAssetIds.size === 0 || removingSelectionTags" @click="openRemoveTagModal">
            <LoaderCircle v-if="removingSelectionTags" class="spin" :size="17" />
            <FilterX v-else :size="17" />
            {{ removingSelectionTags ? t('album.removingTagsFromSelection') : removeTagsActionLabel }}
          </button>
          <button
            v-if="currentAlbum"
            class="secondary-button"
            :disabled="selectedAssetIds.size === 0 || removingFromAlbum"
            @click="removeSelectedFromAlbum"
          >
            <LoaderCircle v-if="removingFromAlbum" class="spin" :size="17" />
            <X v-else :size="17" />
            {{ removingFromAlbum ? t('album.removingFromAlbum') : t('album.removeFromAlbum') }}
          </button>
          <button class="secondary-button" :disabled="selectedAssetIds.size === 0" @click="openCreateAlbumModal">
            <Images :size="17" />
            {{ t('album.createAlbumFromSelection') }}
          </button>
          <button class="primary-button" :disabled="selectedAssetIds.size === 0" @click="shareSelectedAssets">
            <Share2 :size="17" />
            {{ t('album.shareSelected') }}
          </button>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="removeTagOpen" class="modal-backdrop" @click="closeRemoveTagModal">
        <div class="rename-modal" @click.stop>
          <div class="modal-header">
            <strong>{{ t('album.removeTags') }}</strong>
            <button class="icon-button" :title="t('common.close')" @click="closeRemoveTagModal">
              <X :size="18" />
            </button>
          </div>
          <div class="rename-body">
            <label class="rename-label" for="remove-tag-input">{{ t('viewer.tags') }}</label>
            <input
              id="remove-tag-input"
              ref="removeTagInputRef"
              v-model="removeTagInput"
              type="text"
              class="rename-input"
              maxlength="300"
              :placeholder="t('viewer.tagsPlaceholder')"
              @keydown.enter="confirmRemoveTags"
              @keydown.escape="closeRemoveTagModal"
            />
            <div v-if="removeTagPreview.length" class="bulk-tag-preview">
              <span v-for="tag in removeTagPreview" :key="tag" class="bulk-tag-chip remove-tag-chip">{{ tag }}</span>
            </div>
            <p class="modal-subtitle">{{ t('album.removeTagsSelectionHint', { count: selectedAssetIds.size }) }}</p>
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeRemoveTagModal">{{ t('common.cancel') }}</button>
            <button class="primary-button danger-button" :disabled="!removeTagReady || removingSelectionTags" @click="confirmRemoveTags">
              <LoaderCircle v-if="removingSelectionTags" class="spin" :size="17" />
              {{ removingSelectionTags ? t('album.removingTagsFromSelection') : t('album.removeTagsFromSelection') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="renameTagTarget" class="modal-backdrop" @click="closeRenameTag">
        <div class="rename-modal" @click.stop>
          <div class="modal-header">
            <strong>{{ t('album.renameTagTitle') }}</strong>
            <button class="icon-button" :title="t('common.close')" @click="closeRenameTag">
              <X :size="18" />
            </button>
          </div>
          <div class="rename-body">
            <label class="rename-label" for="rename-tag-input">{{ t('album.tagName') }}</label>
            <input
              id="rename-tag-input"
              ref="renameTagInputRef"
              v-model="renameTagName"
              type="text"
              class="rename-input"
              maxlength="40"
              :placeholder="t('viewer.tagsPlaceholder')"
              @keydown.enter="confirmRenameTag"
              @keydown.escape="closeRenameTag"
            />
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeRenameTag">{{ t('common.cancel') }}</button>
            <button class="primary-button" :disabled="!renameTagName.trim() || renamingTag" @click="confirmRenameTag">
              <LoaderCircle v-if="renamingTag" class="spin" :size="17" />
              {{ renamingTag ? t('common.saving') : t('common.save') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="deleteTagTarget" class="modal-backdrop" @click="closeDeleteTag">
        <div class="rename-modal" @click.stop>
          <div class="modal-header">
            <strong>{{ t('album.deleteTagTitle') }}</strong>
            <button class="icon-button" :title="t('common.close')" @click="closeDeleteTag">
              <X :size="18" />
            </button>
          </div>
          <div class="rename-body">
            <p>{{ t('album.confirmDeleteTag', { name: deleteTagTarget.name }) }}</p>
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeDeleteTag">{{ t('common.cancel') }}</button>
            <button class="primary-button danger-button" :disabled="deletingTag" @click="confirmDeleteTag">
              <LoaderCircle v-if="deletingTag" class="spin" :size="17" />
              {{ deletingTag ? t('common.delete') : t('album.deleteTag') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="bulkTagOpen" class="modal-backdrop" @click="closeBulkTagModal">
        <div class="rename-modal" @click.stop>
          <div class="modal-header">
            <strong>{{ t('album.addTags') }}</strong>
            <button class="icon-button" :title="t('common.close')" @click="closeBulkTagModal">
              <X :size="18" />
            </button>
          </div>
          <div class="rename-body">
            <label class="rename-label" for="bulk-tag-input">{{ t('viewer.tags') }}</label>
            <input
              id="bulk-tag-input"
              ref="bulkTagInputRef"
              v-model="bulkTagInput"
              type="text"
              class="rename-input"
              maxlength="300"
              :placeholder="t('viewer.tagsPlaceholder')"
              @keydown.enter="confirmBulkTags"
              @keydown.escape="closeBulkTagModal"
            />
            <div v-if="bulkTagPreview.length" class="bulk-tag-preview">
              <span v-for="tag in bulkTagPreview" :key="tag" class="bulk-tag-chip">{{ tag }}</span>
            </div>
            <p class="modal-subtitle">{{ t('album.addTagsSelectionHint', { count: selectedAssetIds.size }) }}</p>
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeBulkTagModal">{{ t('common.cancel') }}</button>
            <button class="primary-button" :disabled="!bulkTagReady || addingSelectionTags" @click="confirmBulkTags">
              <LoaderCircle v-if="addingSelectionTags" class="spin" :size="17" />
              {{ addingSelectionTags ? t('album.addingTagsToSelection') : t('album.addTagsToSelection') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="createAlbumOpen" class="modal-backdrop" @click="closeCreateAlbumModal">
        <div class="rename-modal" @click.stop>
          <div class="modal-header">
            <strong>{{ t('album.addToAlbum') }}</strong>
            <button class="icon-button" :title="t('common.close')" @click="closeCreateAlbumModal">
              <X :size="18" />
            </button>
          </div>
          <div class="rename-body">
            <div v-if="photoAlbums.length" class="album-target-list">
              <label class="library-filter album-target-filter">
                <Search :size="16" />
                <input v-model="albumTargetFilter" :placeholder="t('album.filterTargetAlbums')" />
                <button v-if="albumTargetFilter" class="search-clear" type="button" :title="t('album.clearAlbumFilter')" @click="albumTargetFilter = ''">
                  <X :size="14" />
                </button>
              </label>
              <button
                v-for="album in filteredTargetAlbums"
                :key="album.id"
                type="button"
                class="album-target-option"
                :class="{ active: selectedTargetAlbumId === album.id }"
                @click="selectTargetAlbum(album.id)"
              >
                <Images :size="17" />
                <span>{{ album.name }}</span>
                <small>{{ formatCount(album.asset_count, 'media') }}</small>
              </button>
              <div v-if="!filteredTargetAlbums.length" class="album-target-empty">
                <Search :size="18" />
                <span>{{ t('album.noAlbumsMatch', { query: albumTargetFilter.trim() }) }}</span>
              </div>
            </div>
            <div class="modal-divider">
              <span>{{ photoAlbums.length ? t('album.orCreateAlbum') : t('album.createFirstAlbum') }}</span>
            </div>
            <label class="rename-label" for="album-name-input">{{ t('album.albumName') }}</label>
            <input
              id="album-name-input"
              ref="albumNameInputRef"
              v-model="createAlbumName"
              type="text"
              class="rename-input"
              maxlength="120"
              :placeholder="t('album.albumNamePlaceholder')"
              @keydown.enter="confirmCreateAlbum"
              @keydown.escape="closeCreateAlbumModal"
            />
            <p class="modal-subtitle">{{ t('album.addAlbumSelectionHint', { count: albumCreateCount }) }}</p>
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeCreateAlbumModal">{{ t('common.cancel') }}</button>
            <button class="primary-button" :disabled="!albumTargetReady || creatingAlbum" @click="confirmCreateAlbum">
              <LoaderCircle v-if="creatingAlbum" class="spin" :size="17" />
              {{ creatingAlbum ? t('album.addingToAlbum') : albumConfirmLabel }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="newAlbumOpen" class="modal-backdrop" @click="closeNewAlbumModal">
        <div class="rename-modal" @click.stop>
          <div class="modal-header">
            <strong>{{ t('album.newAlbum') }}</strong>
            <button class="icon-button" :title="t('common.close')" @click="closeNewAlbumModal">
              <X :size="18" />
            </button>
          </div>
          <div class="rename-body">
            <label class="rename-label" for="new-album-name">{{ t('album.albumName') }}</label>
            <input
              id="new-album-name"
              ref="newAlbumNameInputRef"
              v-model="newAlbumName"
              type="text"
              class="rename-input"
              maxlength="120"
              :placeholder="t('album.albumNamePlaceholder')"
              @keydown.enter="confirmNewAlbum"
              @keydown.escape="closeNewAlbumModal"
            />
            <label class="rename-label" for="new-album-description">{{ t('album.albumDescription') }}</label>
            <textarea
              id="new-album-description"
              v-model="newAlbumDescription"
              class="rename-input album-description-input"
              maxlength="500"
              rows="3"
              :placeholder="t('album.albumDescriptionPlaceholder')"
              @keydown.escape="closeNewAlbumModal"
            ></textarea>
            <p class="modal-subtitle">{{ t('album.newAlbumHint') }}</p>
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeNewAlbumModal">{{ t('common.cancel') }}</button>
            <button class="primary-button" :disabled="!newAlbumName.trim() || creatingNewAlbum" @click="confirmNewAlbum">
              <LoaderCircle v-if="creatingNewAlbum" class="spin" :size="17" />
              {{ creatingNewAlbum ? t('album.creatingAlbum') : t('album.createAlbum') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="albumAssetPickerOpen" class="modal-backdrop" @click="closeAlbumAssetPicker">
        <div class="asset-picker-modal" @click.stop>
          <div class="modal-header">
            <div>
              <strong>{{ t('album.addMediaToAlbum') }}</strong>
              <span class="modal-subtitle">{{ currentAlbum?.name }}</span>
            </div>
            <button class="icon-button" :title="t('common.close')" @click="closeAlbumAssetPicker">
              <X :size="18" />
            </button>
          </div>
          <div class="asset-picker-toolbar">
            <label class="library-filter asset-picker-search">
              <Search :size="16" />
              <input
                ref="albumAssetPickerSearchInputRef"
                v-model="albumAssetPickerSearch"
                :placeholder="t('album.findMediaToAdd')"
                @input="queueAlbumAssetPickerSearch"
                @keydown.escape="closeAlbumAssetPicker"
              />
              <button
                v-if="albumAssetPickerSearch"
                class="search-clear"
                type="button"
                :title="t('common.clearSearch')"
                @click="clearAlbumAssetPickerSearch"
              >
                <X :size="14" />
              </button>
            </label>
            <button class="secondary-button" :disabled="!albumAssetPickerCandidates.length || allAlbumPickerVisibleSelected" @click="selectAllAlbumPickerVisible">
              <ListChecks :size="17" />
              {{ t('album.selectVisibleMedia') }}
            </button>
            <button class="secondary-button" :disabled="!albumAssetPickerSelectedIds.size" @click="clearAlbumAssetPickerSelection">
              <X :size="17" />
              {{ t('album.clearSelected') }}
            </button>
          </div>
          <div class="asset-picker-summary">
            <span>{{ albumAssetPickerSummary }}</span>
          </div>
          <div v-if="albumAssetPickerLoading" class="asset-picker-empty">
            <LoaderCircle class="spin" :size="28" />
            <span>{{ t('album.loadingPhotos') }}</span>
          </div>
          <div v-else-if="albumAssetPickerError" class="asset-picker-empty">
            <ImageOff :size="32" />
            <span>{{ albumAssetPickerError }}</span>
            <button class="secondary-button" @click="loadAlbumAssetPickerCandidates()">
              <RefreshCw :size="17" />
              {{ t('common.tryAgain') }}
            </button>
          </div>
          <div v-else-if="!albumAssetPickerCandidates.length" class="asset-picker-empty">
            <ImageOff :size="32" />
            <span>{{ albumAssetPickerEmptyText }}</span>
          </div>
          <div v-else class="asset-picker-grid">
            <button
              v-for="asset in albumAssetPickerCandidates"
              :key="asset.id"
              type="button"
              class="asset-picker-item"
              :class="{ selected: albumAssetPickerSelectedIds.has(asset.id) }"
              @click="toggleAlbumPickerAsset(asset.id)"
            >
              <span class="asset-picker-thumb">
                <img :src="thumbnailUrl(asset.id, 'small')" :alt="asset.filename" loading="lazy" />
                <span v-if="isVideoAsset(asset)" class="photo-media-badge" :title="t('album.videoAsset')">
                  <Play :size="14" fill="currentColor" />
                </span>
                <span class="photo-select-check" :class="{ checked: albumAssetPickerSelectedIds.has(asset.id) }">
                  <Check v-if="albumAssetPickerSelectedIds.has(asset.id)" :size="17" />
                </span>
                <span v-if="asset.rating > 0" class="photo-rating-badge" :title="ratingLabel(asset.rating)">
                  <Star :size="13" fill="currentColor" />
                  {{ asset.rating }}
                </span>
              </span>
              <span class="asset-picker-name">{{ asset.filename }}</span>
              <span class="asset-picker-meta">{{ assetDateLabel(asset) }}</span>
              <span v-if="assetSourceLabel(asset)" class="asset-picker-source">{{ assetSourceLabel(asset) }}</span>
            </button>
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeAlbumAssetPicker">{{ t('common.cancel') }}</button>
            <button class="primary-button" :disabled="!albumAssetPickerSelectedIds.size || addingAlbumPickerAssets" @click="confirmAlbumAssetPicker">
              <LoaderCircle v-if="addingAlbumPickerAssets" class="spin" :size="17" />
              {{ addingAlbumPickerAssets ? t('album.addingToAlbum') : t('album.addSelectedToAlbum') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="editAlbumTarget" class="modal-backdrop" @click="closeEditAlbum">
        <div class="rename-modal" @click.stop>
          <div class="modal-header">
            <strong>{{ t('album.editAlbum') }}</strong>
            <button class="icon-button" :title="t('common.close')" @click="closeEditAlbum">
              <X :size="18" />
            </button>
          </div>
          <div class="rename-body">
            <label class="rename-label" for="edit-album-name">{{ t('album.albumName') }}</label>
            <input
              id="edit-album-name"
              ref="editAlbumNameInputRef"
              v-model="editAlbumName"
              type="text"
              class="rename-input"
              maxlength="120"
              @keydown.enter="confirmEditAlbum"
              @keydown.escape="closeEditAlbum"
            />
            <label class="rename-label" for="edit-album-description">{{ t('album.albumDescription') }}</label>
            <textarea
              id="edit-album-description"
              v-model="editAlbumDescription"
              class="rename-input album-description-input"
              maxlength="500"
              rows="3"
              :placeholder="t('album.albumDescriptionPlaceholder')"
              @keydown.escape="closeEditAlbum"
            ></textarea>
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeEditAlbum">{{ t('common.cancel') }}</button>
            <button class="primary-button" :disabled="!editAlbumName.trim() || savingAlbum" @click="confirmEditAlbum">
              <LoaderCircle v-if="savingAlbum" class="spin" :size="17" />
              {{ savingAlbum ? t('common.saving') : t('common.save') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="deleteAlbumTarget" class="modal-backdrop" @click="closeDeleteAlbum">
        <div class="rename-modal" @click.stop>
          <div class="modal-header">
            <strong>{{ t('album.deleteAlbum') }}</strong>
            <button class="icon-button" :title="t('common.close')" @click="closeDeleteAlbum">
              <X :size="18" />
            </button>
          </div>
          <div class="rename-body">
            <p>{{ t('album.confirmDeleteAlbum', { name: deleteAlbumTarget.name }) }}</p>
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeDeleteAlbum">{{ t('common.cancel') }}</button>
            <button class="primary-button danger-button" :disabled="deletingAlbum" @click="confirmDeleteAlbum">
              <LoaderCircle v-if="deletingAlbum" class="spin" :size="17" />
              {{ deletingAlbum ? t('album.deletingAlbum') : t('common.delete') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="contextMenuFolder"
        class="context-menu-backdrop"
        @click="closeContextMenu"
        @contextmenu.prevent="closeContextMenu"
      />
      <ul
        v-if="contextMenuFolder"
        class="context-menu"
        :style="{ left: contextMenuPos.x + 'px', top: contextMenuPos.y + 'px' }"
      >
        <li>
          <button @click="openCoverPicker(contextMenuFolder!)">
            <Images :size="16" />
            {{ t('album.changeCover') }}
          </button>
        </li>
        <li>
          <button @click="openRenameModal(contextMenuFolder!)">
            <Pencil :size="16" />
            {{ t('album.renameFolder') }}
          </button>
        </li>
      </ul>
    </Teleport>

    <Teleport to="body">
      <div v-if="coverPickerFolder" class="modal-backdrop" @click="closeCoverPicker">
        <div class="cover-picker-modal" @click.stop>
          <div class="modal-header">
            <div>
              <strong>{{ t('album.selectCoverPhoto') }}</strong>
              <span class="modal-subtitle">{{ coverPickerFolder.name }}</span>
            </div>
            <button class="icon-button" :title="t('common.close')" @click="closeCoverPicker">
              <X :size="18" />
            </button>
          </div>
          <div v-if="coverPickerLoading" class="cover-picker-loading">
            <LoaderCircle class="spin" :size="28" />
            <span>{{ t('album.loadingPhotos') }}</span>
          </div>
          <div v-else-if="!coverPickerAssets.length" class="cover-picker-empty">
            <ImageOff :size="32" />
            <span>{{ t('album.noPhotosHere') }}</span>
          </div>
          <div v-else class="cover-picker-grid">
            <button
              v-for="asset in coverPickerAssets"
              :key="asset.id"
              class="cover-picker-item"
              :class="{ selected: asset.id === coverPickerFolder.cover_asset_id }"
              @click="selectCover(asset.id)"
            >
              <img :src="thumbnailUrl(asset.id, 'small')" :alt="asset.filename" loading="lazy" />
              <span v-if="asset.id === coverPickerFolder.cover_asset_id" class="current-cover-badge">
                {{ t('album.currentCover') }}
              </span>
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="renameFolder" class="modal-backdrop" @click="closeRenameModal">
        <div class="rename-modal" @click.stop>
          <div class="modal-header">
            <strong>{{ t('album.renameFolderTitle') }}</strong>
            <button class="icon-button" :title="t('common.close')" @click="closeRenameModal">
              <X :size="18" />
            </button>
          </div>
          <div class="rename-body">
            <label class="rename-label" for="rename-input">{{ t('album.folderName') }}</label>
            <input
              id="rename-input"
              ref="renameInputRef"
              v-model="renameName"
              type="text"
              class="rename-input"
              :placeholder="renameFolder.name"
              maxlength="120"
              @keydown.enter="confirmRename"
              @keydown.escape="closeRenameModal"
            />
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeRenameModal">{{ t('common.cancel') }}</button>
            <button class="primary-button" :disabled="!renameName.trim()" @click="confirmRename">
              {{ t('album.rename') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="shareCreateTarget" class="modal-backdrop" @click="closeShareCreate">
        <div class="rename-modal" @click.stop>
          <div class="modal-header">
            <strong>{{ t('album.createShareLink') }}</strong>
            <button class="icon-button" :title="t('common.close')" @click="closeShareCreate">
              <X :size="18" />
            </button>
          </div>
          <div class="rename-body">
            <label class="rename-label">{{ t('album.shareTitleLabel') }}</label>
            <input
              v-model="shareCreateTitle"
              type="text"
              class="rename-input"
              maxlength="160"
              @keydown.escape="closeShareCreate"
            />
            <label class="rename-label" style="margin-top: 0.75rem">{{ t('album.shareExpiryLabel') }}</label>
            <select v-model="shareCreateExpiry" class="rename-input">
              <option :value="1">{{ t('album.shareExpiry1Day') }}</option>
              <option :value="7">{{ t('album.shareExpiry7Days') }}</option>
              <option :value="30">{{ t('album.shareExpiry30Days') }}</option>
              <option :value="90">{{ t('album.shareExpiry90Days') }}</option>
              <option :value="365">{{ t('album.shareExpiry365Days') }}</option>
              <option :value="0">{{ t('album.shareExpiryNever') }}</option>
            </select>
            <label class="rename-label" style="margin-top: 0.75rem">{{ t('album.sharePasswordLabel') }}</label>
            <input
              v-model="shareCreatePassword"
              type="password"
              class="rename-input"
              maxlength="128"
              :placeholder="t('album.sharePasswordPlaceholder')"
              @keydown.escape="closeShareCreate"
            />
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeShareCreate">{{ t('common.cancel') }}</button>
            <button class="primary-button" @click="confirmCreateShare">{{ t('album.createShareLink') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="editShareTarget" class="modal-backdrop" @click="closeEditShare">
        <div class="rename-modal" @click.stop>
          <div class="modal-header">
            <strong>{{ t('album.editShareLink') }}</strong>
            <button class="icon-button" :title="t('common.close')" @click="closeEditShare">
              <X :size="18" />
            </button>
          </div>
          <div class="rename-body">
            <label class="rename-label">{{ t('album.shareTitleLabel') }}</label>
            <input
              v-model="editShareTitle"
              type="text"
              class="rename-input"
              maxlength="160"
              @keydown.escape="closeEditShare"
            />
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
            <input
              v-model="editSharePassword"
              type="password"
              class="rename-input"
              maxlength="128"
              :placeholder="t('album.sharePasswordPlaceholder')"
              @keydown.escape="closeEditShare"
            />
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeEditShare">{{ t('common.cancel') }}</button>
            <button class="primary-button" @click="confirmEditShare">{{ t('common.save') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="deleteShareTarget" class="modal-backdrop" @click="closeDeleteShare">
        <div class="rename-modal" @click.stop>
          <div class="modal-header">
            <strong>{{ t('common.delete') }}</strong>
            <button class="icon-button" :title="t('common.close')" @click="closeDeleteShare">
              <X :size="18" />
            </button>
          </div>
          <div class="rename-body">
            <p>{{ t('album.confirmDeleteShare') }}</p>
          </div>
          <div class="rename-footer">
            <button class="secondary-button" @click="closeDeleteShare">{{ t('common.cancel') }}</button>
            <button class="primary-button danger-button" @click="confirmDeleteShare">{{ t('common.delete') }}</button>
          </div>
        </div>
      </div>
    </Teleport>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import {
  Aperture,
  ArrowDownAZ,
  ArrowUpAZ,
  Camera,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Download,
  FilterX,
  Folder,
  FolderOpen,
  FolderRoot,
  FolderTree,
  Grid2X2,
  HardDrive,
  ImageOff,
  Images,
  LayoutGrid,
  Link2,
  ListChecks,
  LoaderCircle,
  LogOut,
  MapPin,
  Maximize2,
  Moon,
  PanelLeft,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Share2,
  Star,
  Sun,
  Tag,
  Trash2,
  Video,
  X,
} from 'lucide-vue-next';
import LanguageToggle from '../components/LanguageToggle.vue';
import PhotoViewer from '../components/PhotoViewer.vue';
import { useLocale } from '../composables/useLocale';
import { useTheme } from '../composables/useTheme';
import { api, thumbnailUrl } from '../services/api';
import type { Asset, AssetCamera, AssetLens, AssetPlace, AssetRating, AssetTag, Folder as FolderType, PhotoAlbum, ShareLink, User } from '../types';

type ThumbSize = 'small' | 'medium' | 'large';
type SortMode = 'date' | 'name' | 'size';
type SortDirection = 'asc' | 'desc';
type AlbumSortMode = 'updated' | 'name' | 'count';
type MediaFilter = 'all' | 'image' | 'video';
type ShareStatusFilter = 'all' | 'active' | 'never' | 'expiring' | 'expired';
type PlaceCluster = {
  key: string;
  label: string;
  latitude: number;
  longitude: number;
  assetCount: number;
  coverAssetId: number | null;
  latestAt: number;
};

const router = useRouter();
const { isDark, toggleTheme } = useTheme();
const { t, formatCount, formatDate } = useLocale();
const user = ref<User | null>(null);
const rootFolders = ref<FolderType[]>([]);
const childFolders = ref<FolderType[]>([]);
const currentFolder = ref<FolderType | null>(null);
const assets = ref<Asset[]>([]);
const search = ref('');
const libraryFilter = ref('');
const albumFilter = ref('');
const tagFilter = ref('');
const favoriteFilter = ref(false);
const ratingFilter = ref(0);
const favoritesView = ref(false);
const allPhotosView = ref(false);
const recentView = ref(false);
const videosView = ref(false);
const placesView = ref(false);
const albumOverviewView = ref(false);
const currentPlace = ref<PlaceCluster | null>(null);
const currentTag = ref<string | null>(null);
const currentRating = ref<number | null>(null);
const currentCamera = ref<AssetCamera | null>(null);
const currentLens = ref<AssetLens | null>(null);
const currentAlbum = ref<PhotoAlbum | null>(null);
const photoAlbums = ref<PhotoAlbum[]>([]);
const albumsLoading = ref(false);
const assetTags = ref<AssetTag[]>([]);
const tagsLoading = ref(false);
const assetRatings = ref<AssetRating[]>([]);
const ratingsLoading = ref(false);
const assetCameras = ref<AssetCamera[]>([]);
const camerasLoading = ref(false);
const assetLenses = ref<AssetLens[]>([]);
const lensesLoading = ref(false);
const assetPlaces = ref<AssetPlace[]>([]);
const includeSubfolders = ref(false);
const mediaFilter = ref<MediaFilter>(storedMediaFilter());
const thumbSize = ref<ThumbSize>(storedThumbSize());
const sortMode = ref<SortMode>(storedSortMode());
const sortDirection = ref<SortDirection>(storedSortDirection());
const albumSortMode = ref<AlbumSortMode>(storedAlbumSortMode());
const albumSortDirection = ref<SortDirection>(storedAlbumSortDirection());
const loading = ref(true);
const searchLoading = ref(false);
const error = ref('');
const viewerIndex = ref<number | null>(null);
const mobileTree = ref(false);
const toastMessage = ref('');
let toastTimer: ReturnType<typeof setTimeout> | null = null;
let searchTimer: ReturnType<typeof setTimeout> | null = null;
let assetRequestId = 0;
const assetsPageSize = 200;
const assetsOffset = ref(0);
const loadingMore = ref(false);
let albumAssetPickerSearchTimer: ReturnType<typeof setTimeout> | null = null;
let albumAssetPickerRequestId = 0;

const contextMenuFolder = ref<FolderType | null>(null);
const contextMenuPos = ref({ x: 0, y: 0 });
const coverPickerFolder = ref<FolderType | null>(null);
const coverPickerAssets = ref<Asset[]>([]);
const coverPickerLoading = ref(false);
const renameFolder = ref<FolderType | null>(null);
const renameName = ref('');
const renameInputRef = ref<HTMLInputElement | null>(null);
const newAlbumOpen = ref(false);
const newAlbumName = ref('');
const newAlbumDescription = ref('');
const newAlbumNameInputRef = ref<HTMLInputElement | null>(null);
const creatingNewAlbum = ref(false);
const createAlbumOpen = ref(false);
const createAlbumName = ref('');
const createAlbumAssetIds = ref<number[]>([]);
const createAlbumSource = ref<'selection' | 'viewer' | null>(null);
const selectedTargetAlbumId = ref<number | null>(null);
const albumTargetFilter = ref('');
const creatingAlbum = ref(false);
const albumNameInputRef = ref<HTMLInputElement | null>(null);
const albumAssetPickerOpen = ref(false);
const albumAssetPickerSearch = ref('');
const albumAssetPickerCandidates = ref<Asset[]>([]);
const albumAssetPickerExistingIds = ref(new Set<number>());
const albumAssetPickerSelectedIds = ref(new Set<number>());
const albumAssetPickerLoading = ref(false);
const albumAssetPickerError = ref('');
const addingAlbumPickerAssets = ref(false);
const albumAssetPickerSearchInputRef = ref<HTMLInputElement | null>(null);
const bulkTagOpen = ref(false);
const bulkTagInput = ref('');
const bulkTagInputRef = ref<HTMLInputElement | null>(null);
const addingSelectionTags = ref(false);
const removeTagOpen = ref(false);
const removeTagInput = ref('');
const removeTagInputRef = ref<HTMLInputElement | null>(null);
const removingSelectionTags = ref(false);
const renameTagTarget = ref<AssetTag | null>(null);
const renameTagName = ref('');
const renameTagInputRef = ref<HTMLInputElement | null>(null);
const renamingTag = ref(false);
const deleteTagTarget = ref<AssetTag | null>(null);
const deletingTag = ref(false);
const editAlbumTarget = ref<PhotoAlbum | null>(null);
const editAlbumName = ref('');
const editAlbumDescription = ref('');
const editAlbumNameInputRef = ref<HTMLInputElement | null>(null);
const savingAlbum = ref(false);
const selectionMode = ref(false);
const selectedAssetIds = ref(new Set<number>());
const lastSelectedAssetIndex = ref<number | null>(null);
const downloadingSelection = ref(false);
const updatingSelectionFavorite = ref(false);
const removingFromAlbum = ref(false);
const sharingAlbum = ref(false);
const showSharesPanel = ref(false);
const collapsedSections = ref<Record<string, boolean>>({
  albums: true,
  cameras: true,
  lenses: true,
  ratings: true,
  tags: true,
});
const myShares = ref<ShareLink[]>([]);
const sharesLoading = ref(false);
const shareFilter = ref('');
const shareStatusFilter = ref<ShareStatusFilter>('all');
const shareCreateTarget = ref<{ asset_id?: number; folder_id?: number; asset_ids?: number[] } | null>(null);
const shareCreateTitle = ref('');
const shareCreateExpiry = ref(7);
const shareCreatePassword = ref<string | undefined>(undefined);
const editShareTarget = ref<ShareLink | null>(null);
const editShareTitle = ref('');
const editShareExpiry = ref(7);
const editSharePassword = ref<string | undefined>(undefined);
const deleteShareTarget = ref<ShareLink | null>(null);
const deleteAlbumTarget = ref<PhotoAlbum | null>(null);
const deletingAlbum = ref(false);
const ratingOptions = [1, 2, 3, 4, 5];

const tileSize = computed(() => {
  if (thumbSize.value === 'small') return '150px';
  if (thumbSize.value === 'large') return '260px';
  return '200px';
});

const placeOverviewActive = computed(() => placesView.value && !currentPlace.value);
const placeClusters = computed(() => assetPlaces.value.map(placeFromApi));
const displayedPlaceClusters = computed(() => sortPlaceClusters(placeClusters.value));
const displayAssets = computed(() => {
  const source = placeOverviewActive.value ? [] : assets.value;
  const sorted = [...source];
  if (sortMode.value === 'name') {
    return sorted.sort((a, b) => compareByDirection(a.filename.localeCompare(b.filename)));
  }
  if (sortMode.value === 'size') {
    return sorted.sort((a, b) => compareByDirection(a.size - b.size));
  }
  return sorted.sort((a, b) => {
    const left = Date.parse(a.captured_at || a.updated_at) || a.mtime || 0;
    const right = Date.parse(b.captured_at || b.updated_at) || b.mtime || 0;
    return compareByDirection(left - right);
  });
});
const searchQuery = computed(() => search.value.trim());
const hasSearch = computed(() => searchQuery.value.length > 0);
const globalSearchActive = computed(
  () =>
    !currentFolder.value &&
    !favoritesView.value &&
    !allPhotosView.value &&
    !recentView.value &&
    !videosView.value &&
    !placesView.value &&
    !currentTag.value &&
    !currentRating.value &&
    !currentCamera.value &&
    !currentLens.value &&
    !currentAlbum.value &&
    hasSearch.value,
);
const favoritesOnlyActive = computed(() => favoritesView.value || favoriteFilter.value);
const showAssetSource = computed(
  () =>
    globalSearchActive.value ||
    favoritesView.value ||
    allPhotosView.value ||
    recentView.value ||
    videosView.value ||
    placesView.value ||
    Boolean(currentTag.value) ||
    Boolean(currentRating.value) ||
    Boolean(currentCamera.value) ||
    Boolean(currentLens.value) ||
    Boolean(currentAlbum.value) ||
    includeSubfolders.value,
);
const visibleChildFolders = computed(() =>
  favoritesOnlyActive.value || allPhotosView.value || recentView.value || videosView.value || placesView.value || currentTag.value || currentRating.value || currentCamera.value || currentLens.value || currentAlbum.value || globalSearchActive.value
    ? []
    : childFolders.value,
);
const visibleMediaCount = computed(() =>
  placeOverviewActive.value
    ? assetPlaces.value.reduce((count, place) => count + place.asset_count, 0)
    : displayAssets.value.length,
);
const albumOverviewMediaCount = computed(() => filteredPhotoAlbums.value.reduce((count, album) => count + album.asset_count, 0));
const hasVisibleContent = computed(() => (placeOverviewActive.value ? displayedPlaceClusters.value.length > 0 : displayAssets.value.length > 0));
const canLoadMoreAssets = computed(() => assets.value.length >= assetsPageSize && !loadingMore.value && !currentAlbum.value && !albumOverviewView.value);
const sortDirectionTitle = computed(() => (sortDirection.value === 'asc' ? t('common.ascendingOrder') : t('common.descendingOrder')));
const activeMediaFilter = computed<MediaFilter>(() => (videosView.value ? 'video' : mediaFilter.value));
const effectiveRatingFilter = computed(() => Math.max(currentRating.value ?? 0, ratingFilter.value));
const hasActiveAssetFilters = computed(
  () => Boolean(search.value.trim() || activeMediaFilter.value !== 'all' || favoriteFilter.value || includeSubfolders.value || ratingFilter.value > (currentRating.value ?? 0)),
);
const assetActionsEnabled = computed(() =>
  Boolean(currentFolder.value || favoritesView.value || allPhotosView.value || recentView.value || videosView.value || currentPlace.value || currentTag.value || currentRating.value || currentCamera.value || currentLens.value || currentAlbum.value || globalSearchActive.value),
);
const pageEyebrow = computed(() => {
  if (currentAlbum.value) return t('album.albumEyebrow');
  if (albumOverviewView.value) return t('album.albumEyebrow');
  if (currentTag.value) return t('album.smartAlbum');
  if (currentRating.value) return t('album.smartAlbum');
  if (currentCamera.value) return t('album.smartAlbum');
  if (currentLens.value) return t('album.smartAlbum');
  if (recentView.value) return t('album.smartAlbum');
  if (videosView.value) return t('album.smartAlbum');
  if (placesView.value) return t('album.smartAlbum');
  if (allPhotosView.value) return t('album.smartAlbum');
  if (favoritesView.value) return t('album.smartAlbum');
  if (globalSearchActive.value) return t('album.searchEyebrow');
  return t('album.libraryEyebrow');
});
const pageTitle = computed(() => {
  if (currentAlbum.value) return currentAlbum.value.name;
  if (currentTag.value) return currentTag.value;
  if (currentRating.value) return t('album.ratingAtLeast', { rating: currentRating.value });
  if (currentCamera.value) return currentCamera.value.label;
  if (currentLens.value) return currentLens.value.label;
  if (currentPlace.value) return currentPlace.value.label;
  if (recentView.value) return t('album.recentlyAdded');
  if (videosView.value) return t('album.videos');
  if (placesView.value) return t('album.places');
  if (albumOverviewView.value) return t('album.albums');
  if (allPhotosView.value) return t('album.allPhotos');
  if (favoritesView.value) return t('album.favorites');
  if (globalSearchActive.value) return t('album.searchResults');
  return currentFolder.value?.name || t('album.allLibraries');
});
const hasAlbumDescription = computed(() => Boolean(currentAlbum.value?.description.trim()));
const albumDescriptionText = computed(() => (hasAlbumDescription.value ? currentAlbum.value?.description.trim() ?? '' : t('album.noAlbumDescription')));
const albumUpdatedLabel = computed(() => formatDate(currentAlbum.value?.updated_at));
const albumCreatedLabel = computed(() => formatDate(currentAlbum.value?.created_at));
const searchPlaceholder = computed(() => {
  if (currentAlbum.value) return t('album.searchThisAlbum');
  if (currentTag.value) return t('album.searchTaggedPhotos');
  if (currentRating.value) return t('album.searchRatedPhotos');
  if (currentCamera.value) return t('album.searchCameraPhotos');
  if (currentLens.value) return t('album.searchLensPhotos');
  if (currentPlace.value) return t('album.searchThisPlace');
  if (recentView.value) return t('album.searchRecentlyAdded');
  if (videosView.value) return t('album.searchVideos');
  if (placesView.value) return t('album.searchPlaces');
  if (allPhotosView.value) return t('album.searchAllPhotos');
  if (favoritesView.value) return t('album.searchFavorites');
  return currentFolder.value ? t('album.searchThisFolder') : t('album.searchAllLibraries');
});
const favoriteEmptyHint = computed(() => (favoritesView.value ? t('album.noGlobalFavoritePhotosHint') : t('album.noFavoritePhotosHint')));
const emptyStateTitle = computed(() => {
  if (hasSearch.value) return t('album.noMatchesFound');
  if (albumOverviewView.value) return t('album.noAlbums');
  if (favoritesOnlyActive.value) return t('album.noFavoritePhotos');
  if (placesView.value) return t('album.noLocationPhotos');
  if (currentTag.value) return t('album.noTaggedPhotos');
  if (currentRating.value) return t('album.noRatedPhotos');
  if (currentCamera.value) return t('album.noCameraPhotos');
  if (currentLens.value) return t('album.noLensPhotos');
  return t('album.noPhotosHere');
});
const searchEmptyHint = computed(() =>
  globalSearchActive.value || allPhotosView.value || recentView.value || videosView.value || placesView.value || currentTag.value || currentRating.value || currentCamera.value || currentLens.value
    ? t('album.nothingMatchesAllLibraries', { query: searchQuery.value })
    : currentAlbum.value
      ? t('album.nothingMatchesAlbum', { query: searchQuery.value })
    : t('album.nothingMatches', { query: searchQuery.value }),
);
const filteredRootFolders = computed(() => {
  const query = libraryFilter.value.trim().toLowerCase();
  if (!query) return rootFolders.value;
  return rootFolders.value.filter((folder) => folder.name.toLowerCase().includes(query));
});
const filteredPhotoAlbums = computed(() => {
  const query = albumFilter.value.trim().toLowerCase();
  const albums = query
    ? photoAlbums.value.filter((album) =>
        [album.name, album.description].some((value) => value.toLowerCase().includes(query)),
      )
    : photoAlbums.value;
  return sortPhotoAlbums(albums);
});
const filteredAssetTags = computed(() => {
  const query = tagFilter.value.trim().toLowerCase();
  if (!query) return assetTags.value;
  return assetTags.value.filter((tag) => tag.name.toLowerCase().includes(query));
});
const filteredAssetRatings = computed(() =>
  assetRatings.value
    .filter((rating) => rating.asset_count > 0)
    .sort((a, b) => b.rating - a.rating),
);
const filteredAssetCameras = computed(() =>
  assetCameras.value
    .filter((camera) => camera.asset_count > 0)
    .sort((a, b) => b.asset_count - a.asset_count || a.label.localeCompare(b.label)),
);
const filteredAssetLenses = computed(() =>
  assetLenses.value
    .filter((lens) => lens.asset_count > 0)
    .sort((a, b) => b.asset_count - a.asset_count || a.label.localeCompare(b.label)),
);
const filteredTargetAlbums = computed(() => {
  const query = albumTargetFilter.value.trim().toLowerCase();
  if (!query) return photoAlbums.value;
  return photoAlbums.value.filter((album) =>
    [album.name, album.description].some((value) => value.toLowerCase().includes(query)),
  );
});
const filteredMyShares = computed(() => {
  const query = shareFilter.value.trim().toLowerCase();
  return myShares.value.filter((share) => {
    const matchesQuery = !query || shareSearchText(share).includes(query);
    const matchesStatus = shareMatchesStatus(share);
    return matchesQuery && matchesStatus;
  });
});
const libraryListSummary = computed(() => {
  if (!rootFolders.value.length) return t('album.noLibrariesAvailable');
  if (!libraryFilter.value.trim()) return formatCount(rootFolders.value.length, 'library');
  return t('admin.shownPartial', { shown: filteredRootFolders.value.length, total: rootFolders.value.length });
});
const albumSortDirectionTitle = computed(() =>
  albumSortDirection.value === 'asc' ? t('common.ascendingOrder') : t('common.descendingOrder'),
);
const shareEmptyHint = computed(() => {
  const query = shareFilter.value.trim();
  if (query) return t('album.noSharesMatch', { query });
  return t('album.noSharesStatusMatch');
});
const selectedCountLabel = computed(() => {
  const count = selectedAssetIds.value.size;
  return t(count === 1 ? 'album.photoSelected' : 'album.photosSelected', { count });
});
const selectedAssets = computed(() => displayAssets.value.filter((asset) => selectedAssetIds.value.has(asset.id)));
const selectedFavoritesTarget = computed(() => selectedAssets.value.some((asset) => !asset.is_favorite));
const selectedFavoriteActionLabel = computed(() =>
  selectedFavoritesTarget.value ? t('album.favoriteSelected') : t('album.unfavoriteSelected'),
);
const albumCreateCount = computed(() => createAlbumAssetIds.value.length);
const albumTargetReady = computed(() => albumCreateCount.value > 0 && Boolean(selectedTargetAlbumId.value || createAlbumName.value.trim()));
const albumConfirmLabel = computed(() => (selectedTargetAlbumId.value ? t('album.addToAlbum') : t('album.createAlbum')));
const albumAssetPickerSearchQuery = computed(() => albumAssetPickerSearch.value.trim());
const allAlbumPickerVisibleSelected = computed(
  () => albumAssetPickerCandidates.value.length > 0 && albumAssetPickerCandidates.value.every((asset) => albumAssetPickerSelectedIds.value.has(asset.id)),
);
const albumAssetPickerSummary = computed(() => {
  const selected = albumAssetPickerSelectedIds.value.size;
  const shown = albumAssetPickerCandidates.value.length;
  if (selected) return t('album.assetPickerSelectionSummary', { selected, shown });
  return t('album.assetPickerShowingSummary', { shown });
});
const albumAssetPickerEmptyText = computed(() =>
  albumAssetPickerSearchQuery.value
    ? t('album.assetPickerNoMatches', { query: albumAssetPickerSearchQuery.value })
    : t('album.assetPickerNoAvailableMedia'),
);
const bulkTagPreview = computed(() => normalizeTagInput(bulkTagInput.value));
const bulkTagReady = computed(() => bulkTagPreview.value.length > 0 && selectedAssetIds.value.size > 0);
const removeTagPreview = computed(() => normalizeTagInput(removeTagInput.value));
const removeTagReady = computed(() => removeTagPreview.value.length > 0 && selectedAssetIds.value.size > 0);
const removeTagsActionLabel = computed(() => (currentTag.value ? t('album.removeFromCurrentTag') : t('album.removeTagsFromSelection')));
const allVisibleAssetsSelected = computed(
  () => displayAssets.value.length > 0 && displayAssets.value.every((asset) => selectedAssetIds.value.has(asset.id)),
);
const viewerShortcutsDisabled = computed(() =>
  Boolean(
    createAlbumOpen.value ||
      newAlbumOpen.value ||
      albumAssetPickerOpen.value ||
      bulkTagOpen.value ||
      removeTagOpen.value ||
      renameTagTarget.value ||
      deleteTagTarget.value ||
      editAlbumTarget.value ||
      deleteAlbumTarget.value ||
      shareCreateTarget.value ||
      editShareTarget.value ||
      deleteShareTarget.value ||
      coverPickerFolder.value ||
      renameFolder.value,
  ),
);

watch(createAlbumName, (value) => {
  if (value.trim()) selectedTargetAlbumId.value = null;
});

watch(albumTargetFilter, () => {
  if (!createAlbumOpen.value || createAlbumName.value.trim()) return;
  if (selectedTargetAlbumId.value && filteredTargetAlbums.value.some((album) => album.id === selectedTargetAlbumId.value)) return;
  selectedTargetAlbumId.value = filteredTargetAlbums.value[0]?.id ?? null;
});

watch(mediaFilter, (value) => localStorage.setItem('dk-photo-media-filter', value));
watch(thumbSize, (value) => localStorage.setItem('dk-photo-thumb-size', value));
watch(sortMode, (value) => localStorage.setItem('dk-photo-sort-mode', value));
watch(sortDirection, (value) => localStorage.setItem('dk-photo-sort-direction', value));
watch(albumSortMode, (value) => localStorage.setItem('dk-photo-album-sort-mode', value));
watch(albumSortDirection, (value) => localStorage.setItem('dk-photo-album-sort-direction', value));

onUnmounted(() => {
  if (toastTimer) window.clearTimeout(toastTimer);
  cancelSearchTimer();
  cancelAlbumAssetPickerSearchTimer();
  window.removeEventListener('keydown', handleAlbumKeydown);
});

onMounted(async () => {
  window.addEventListener('keydown', handleAlbumKeydown);
  try {
    user.value = await api.me();
    await loadTags();
    await loadRatings();
    await loadCameras();
    await loadLenses();
    await loadAlbums();
    await loadRoot();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadApp');
    loading.value = false;
  }
});

async function loadRoot() {
  loading.value = true;
  error.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  assetRequestId += 1;
  currentFolder.value = null;
  currentTag.value = null;
  currentRating.value = null;
  currentAlbum.value = null;
  currentPlace.value = null;
  currentCamera.value = null;
  currentLens.value = null;
  viewerIndex.value = null;
  recentView.value = false;
  videosView.value = false;
  placesView.value = false;
  albumOverviewView.value = false;
  allPhotosView.value = false;
  favoritesView.value = false;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  lastSelectedAssetIndex.value = null;
  try {
    childFolders.value = await api.folders(null);
    rootFolders.value = childFolders.value;
    assets.value = [];
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadLibraries');
  } finally {
    loading.value = false;
  }
}

async function loadAlbums() {
  albumsLoading.value = true;
  try {
    photoAlbums.value = await api.albums();
    if (currentAlbum.value) {
      currentAlbum.value = photoAlbums.value.find((album) => album.id === currentAlbum.value?.id) ?? currentAlbum.value;
    }
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableLoadAlbums'));
  } finally {
    albumsLoading.value = false;
  }
}

async function loadTags() {
  tagsLoading.value = true;
  try {
    assetTags.value = await api.assetTags();
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableLoadTags'));
  } finally {
    tagsLoading.value = false;
  }
}

async function loadRatings() {
  ratingsLoading.value = true;
  try {
    assetRatings.value = await api.assetRatings();
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableLoadRatings'));
  } finally {
    ratingsLoading.value = false;
  }
}

async function loadCameras() {
  camerasLoading.value = true;
  try {
    assetCameras.value = await api.assetCameras();
    if (currentCamera.value) {
      currentCamera.value = assetCameras.value.find((camera) => camera.camera_key === currentCamera.value?.camera_key) ?? currentCamera.value;
    }
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableLoadCameras'));
  } finally {
    camerasLoading.value = false;
  }
}

async function loadLenses() {
  lensesLoading.value = true;
  try {
    assetLenses.value = await api.assetLenses();
    if (currentLens.value) {
      currentLens.value = assetLenses.value.find((lens) => lens.lens_key === currentLens.value?.lens_key) ?? currentLens.value;
    }
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableLoadLenses'));
  } finally {
    lensesLoading.value = false;
  }
}

async function openFolder(folder: FolderType) {
  await openFolderById(folder.id);
}

async function openFolderById(folderId: number, fallbackMessage = t('album.unableOpenFolder')) {
  loading.value = true;
  error.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  assetRequestId += 1;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  currentTag.value = null;
  currentRating.value = null;
  currentAlbum.value = null;
  currentPlace.value = null;
  currentCamera.value = null;
  currentLens.value = null;
  recentView.value = false;
  videosView.value = false;
  placesView.value = false;
  albumOverviewView.value = false;
  allPhotosView.value = false;
  favoritesView.value = false;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  lastSelectedAssetIndex.value = null;
  try {
    currentFolder.value = await api.folder(folderId);
    childFolders.value = await api.folders(folderId);
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : fallbackMessage;
  } finally {
    loading.value = false;
  }
}

function goRoot() {
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  favoriteFilter.value = false;
  currentTag.value = null;
  currentRating.value = null;
  currentAlbum.value = null;
  currentPlace.value = null;
  currentCamera.value = null;
  currentLens.value = null;
  recentView.value = false;
  videosView.value = false;
  placesView.value = false;
  albumOverviewView.value = false;
  allPhotosView.value = false;
  favoritesView.value = false;
  includeSubfolders.value = false;
  mobileTree.value = false;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  loadRoot();
}

async function loadAssets({ showSearchLoading = false }: { showSearchLoading?: boolean } = {}) {
  if (placeOverviewActive.value) {
    await loadPlaces({ showSearchLoading });
    return;
  }
  if (
    !currentFolder.value &&
    !favoritesView.value &&
    !allPhotosView.value &&
    !recentView.value &&
    !videosView.value &&
    !placesView.value &&
    !currentTag.value &&
    !currentRating.value &&
    !currentCamera.value &&
    !currentLens.value &&
    !currentAlbum.value &&
    !globalSearchActive.value
  ) return;
  assetsOffset.value = 0;
  const requestId = ++assetRequestId;
  const folderId = currentFolder.value ? currentFolder.value.id : null;
  const query = searchQuery.value;
  const onlyFavorites = favoritesView.value || favoriteFilter.value;
  const recursive = Boolean(currentFolder.value && includeSubfolders.value && !favoritesView.value);
  const minRating = effectiveRatingFilter.value;
  if (showSearchLoading) searchLoading.value = true;
  try {
    const nextAssets = currentAlbum.value
      ? await api.albumAssets(currentAlbum.value.id, query, { mediaType: mediaFilter.value, minRating })
      : await api.assets(folderId, query, recursive, onlyFavorites, {
          ...(recentView.value ? { sort: 'recent' as const } : {}),
          limit: assetsPageSize,
          mediaType: videosView.value ? 'video' : mediaFilter.value,
          hasLocation: placesView.value,
          tag: currentTag.value ?? undefined,
          minRating,
          camera: currentCamera.value?.camera_key,
          lens: currentLens.value?.lens_key,
          place: currentPlace.value?.key,
        });
    if (requestId !== assetRequestId) return;
    assets.value = nextAssets;
    error.value = '';
  } catch (err) {
    if (requestId === assetRequestId) {
      const fallbackMessage = favoritesView.value
        ? t('album.unableLoadFavorites')
        : videosView.value
          ? t('album.unableLoadVideos')
          : placesView.value
            ? t('album.unableLoadPlaces')
            : currentTag.value
              ? t('album.unableLoadTags')
              : currentRating.value
                ? t('album.unableLoadRatings')
                : currentCamera.value
                  ? t('album.unableLoadCameras')
                  : currentLens.value
                    ? t('album.unableLoadLenses')
                    : t('album.unableLoadPhotos');
      error.value = err instanceof Error ? err.message : fallbackMessage;
    }
  } finally {
    if (requestId === assetRequestId && showSearchLoading) {
      searchLoading.value = false;
    }
  }
}

async function loadMoreAssets() {
  if (loadingMore.value || currentAlbum.value) return;
  const folderId = currentFolder.value ? currentFolder.value.id : null;
  const query = searchQuery.value;
  const onlyFavorites = favoritesView.value || favoriteFilter.value;
  const recursive = Boolean(currentFolder.value && includeSubfolders.value && !favoritesView.value);
  const minRating = effectiveRatingFilter.value;
  loadingMore.value = true;
  const requestId = ++assetRequestId;
  try {
    assetsOffset.value += assetsPageSize;
    const nextAssets = await api.assets(folderId, query, recursive, onlyFavorites, {
      ...(recentView.value ? { sort: 'recent' as const } : {}),
      limit: assetsPageSize,
      offset: assetsOffset.value,
      mediaType: videosView.value ? 'video' : mediaFilter.value,
      hasLocation: placesView.value,
      tag: currentTag.value ?? undefined,
      minRating,
      camera: currentCamera.value?.camera_key,
      lens: currentLens.value?.lens_key,
      place: currentPlace.value?.key,
    });
    if (requestId !== assetRequestId) {
      assetsOffset.value -= assetsPageSize;
      return;
    }
    if (!nextAssets.length) {
      assetsOffset.value -= assetsPageSize;
    } else {
      assets.value = [...assets.value, ...nextAssets];
    }
  } catch {
    assetsOffset.value -= assetsPageSize;
  } finally {
    loadingMore.value = false;
  }
}

async function loadPlaces({ showSearchLoading = false }: { showSearchLoading?: boolean } = {}) {
  const requestId = ++assetRequestId;
  if (showSearchLoading) searchLoading.value = true;
  try {
    const nextPlaces = await api.assetPlaces(searchQuery.value);
    if (requestId !== assetRequestId) return;
    assetPlaces.value = nextPlaces;
    assets.value = [];
    error.value = '';
  } catch (err) {
    if (requestId === assetRequestId) {
      error.value = err instanceof Error ? err.message : t('album.unableLoadPlaces');
    }
  } finally {
    if (requestId === assetRequestId && showSearchLoading) {
      searchLoading.value = false;
    }
  }
}

function queueAssetSearch() {
  cancelSearchTimer();
  if (
    !currentFolder.value &&
    !favoritesView.value &&
    !allPhotosView.value &&
    !recentView.value &&
    !videosView.value &&
    !placesView.value &&
    !currentTag.value &&
    !currentRating.value &&
    !currentCamera.value &&
    !currentLens.value &&
    !currentAlbum.value &&
    !searchQuery.value
  ) {
    assets.value = [];
    error.value = '';
    searchLoading.value = false;
    viewerIndex.value = null;
    selectionMode.value = false;
    selectedAssetIds.value = new Set();
    lastSelectedAssetIndex.value = null;
    return;
  }
  searchLoading.value = true;
  searchTimer = window.setTimeout(() => {
    loadAssets({ showSearchLoading: true });
  }, 280);
}

function clearSearch() {
  if (!search.value) return;
  search.value = '';
  cancelSearchTimer();
  if (currentFolder.value || favoritesView.value || allPhotosView.value || recentView.value || videosView.value || placesView.value || currentTag.value || currentRating.value || currentCamera.value || currentLens.value || currentAlbum.value) {
    loadAssets({ showSearchLoading: true });
  } else {
    assets.value = [];
    error.value = '';
    searchLoading.value = false;
    viewerIndex.value = null;
    selectionMode.value = false;
    selectedAssetIds.value = new Set();
    lastSelectedAssetIndex.value = null;
  }
}

async function clearAssetFilters() {
  const hadSearch = Boolean(search.value.trim());
  search.value = '';
  cancelSearchTimer();
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  mediaFilter.value = 'all';
  ratingFilter.value = currentRating.value ?? 0;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  if (videosView.value) {
    await openAllPhotosView();
    return;
  }
  if (currentFolder.value || favoritesView.value || allPhotosView.value || recentView.value || videosView.value || placesView.value || currentTag.value || currentRating.value || currentCamera.value || currentLens.value || currentAlbum.value || hadSearch) {
    await loadAssets({ showSearchLoading: true });
  }
}

function cancelSearchTimer() {
  if (searchTimer) {
    window.clearTimeout(searchTimer);
    searchTimer = null;
  }
}

async function logout() {
  await api.logout();
  await router.push('/login');
}

function openViewer(index: number) {
  viewerIndex.value = index;
}

function shareAsset(asset: Asset) {
  shareCreateTarget.value = { asset_id: asset.id };
  shareCreateTitle.value = asset.filename;
  shareCreateExpiry.value = 7;
}

function shareCurrentFolder() {
  if (!currentFolder.value) return;
  shareCreateTarget.value = { folder_id: currentFolder.value.id };
  shareCreateTitle.value = currentFolder.value.name;
  shareCreateExpiry.value = 7;
}

async function shareCurrentAlbum() {
  if (!currentAlbum.value || sharingAlbum.value) return;
  const album = currentAlbum.value;
  sharingAlbum.value = true;
  try {
    const albumAssets = await api.albumAssets(album.id);
    if (!albumAssets.length) {
      showToast(t('album.noPhotosHere'));
      return;
    }
    shareCreateTarget.value = { asset_ids: albumAssets.map((asset) => asset.id) };
    shareCreateTitle.value = album.name;
    shareCreateExpiry.value = 7;
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableShareAlbum'));
  } finally {
    sharingAlbum.value = false;
  }
}

async function openAssetFolder(asset: Asset) {
  viewerIndex.value = null;
  search.value = '';
  await openFolderById(asset.folder_id, t('album.unableOpenSourceFolder'));
}

async function openAllPhotosView() {
  loading.value = true;
  error.value = '';
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  currentFolder.value = null;
  childFolders.value = [];
  currentTag.value = null;
  currentRating.value = null;
  currentAlbum.value = null;
  currentPlace.value = null;
  currentCamera.value = null;
  currentLens.value = null;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  favoritesView.value = false;
  recentView.value = false;
  videosView.value = false;
  placesView.value = false;
  albumOverviewView.value = false;
  allPhotosView.value = true;
  try {
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadPhotos');
  } finally {
    loading.value = false;
  }
}

async function openRecentView() {
  loading.value = true;
  error.value = '';
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  currentFolder.value = null;
  childFolders.value = [];
  currentTag.value = null;
  currentRating.value = null;
  currentAlbum.value = null;
  currentPlace.value = null;
  currentCamera.value = null;
  currentLens.value = null;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  favoritesView.value = false;
  allPhotosView.value = false;
  videosView.value = false;
  placesView.value = false;
  albumOverviewView.value = false;
  recentView.value = true;
  try {
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadPhotos');
  } finally {
    loading.value = false;
  }
}

async function openVideosView() {
  loading.value = true;
  error.value = '';
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  currentFolder.value = null;
  childFolders.value = [];
  currentTag.value = null;
  currentRating.value = null;
  currentAlbum.value = null;
  currentPlace.value = null;
  currentCamera.value = null;
  currentLens.value = null;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  favoritesView.value = false;
  allPhotosView.value = false;
  recentView.value = false;
  placesView.value = false;
  albumOverviewView.value = false;
  mediaFilter.value = 'video';
  videosView.value = true;
  try {
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadVideos');
  } finally {
    loading.value = false;
  }
}

async function openAlbumView(album: PhotoAlbum) {
  loading.value = true;
  error.value = '';
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  currentFolder.value = null;
  childFolders.value = [];
  currentTag.value = null;
  currentRating.value = null;
  currentPlace.value = null;
  currentCamera.value = null;
  currentLens.value = null;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  favoritesView.value = false;
  allPhotosView.value = false;
  recentView.value = false;
  videosView.value = false;
  placesView.value = false;
  albumOverviewView.value = false;
  currentAlbum.value = album;
  try {
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadAlbum');
  } finally {
    loading.value = false;
  }
}

async function openFavoritesView() {
  loading.value = true;
  error.value = '';
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  currentFolder.value = null;
  childFolders.value = [];
  currentTag.value = null;
  currentRating.value = null;
  currentAlbum.value = null;
  currentPlace.value = null;
  currentCamera.value = null;
  currentLens.value = null;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  allPhotosView.value = false;
  recentView.value = false;
  videosView.value = false;
  placesView.value = false;
  albumOverviewView.value = false;
  favoritesView.value = true;
  try {
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadFavorites');
  } finally {
    loading.value = false;
  }
}

async function openPlacesView() {
  loading.value = true;
  error.value = '';
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  currentFolder.value = null;
  childFolders.value = [];
  currentTag.value = null;
  currentRating.value = null;
  currentAlbum.value = null;
  currentPlace.value = null;
  currentCamera.value = null;
  currentLens.value = null;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  favoritesView.value = false;
  allPhotosView.value = false;
  recentView.value = false;
  videosView.value = false;
  albumOverviewView.value = false;
  mediaFilter.value = 'all';
  placesView.value = true;
  try {
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadPlaces');
  } finally {
    loading.value = false;
  }
}

async function openAlbumOverviewView() {
  loading.value = true;
  error.value = '';
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  currentFolder.value = null;
  childFolders.value = [];
  currentTag.value = null;
  currentRating.value = null;
  currentAlbum.value = null;
  currentPlace.value = null;
  currentCamera.value = null;
  currentLens.value = null;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  favoritesView.value = false;
  allPhotosView.value = false;
  recentView.value = false;
  videosView.value = false;
  placesView.value = false;
  albumOverviewView.value = true;
  assets.value = [];
  try {
    await loadAlbums();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadAlbums');
  } finally {
    loading.value = false;
  }
}

async function openTagView(tagName: string) {
  loading.value = true;
  error.value = '';
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  currentFolder.value = null;
  childFolders.value = [];
  currentAlbum.value = null;
  currentPlace.value = null;
  currentRating.value = null;
  currentCamera.value = null;
  currentLens.value = null;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  favoritesView.value = false;
  allPhotosView.value = false;
  recentView.value = false;
  videosView.value = false;
  placesView.value = false;
  albumOverviewView.value = false;
  mediaFilter.value = 'all';
  currentTag.value = tagName;
  try {
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadTags');
  } finally {
    loading.value = false;
  }
}

async function openRatingView(rating: number) {
  const normalizedRating = Math.min(5, Math.max(1, Math.trunc(rating)));
  loading.value = true;
  error.value = '';
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  currentFolder.value = null;
  childFolders.value = [];
  currentTag.value = null;
  currentAlbum.value = null;
  currentPlace.value = null;
  currentCamera.value = null;
  currentLens.value = null;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  favoritesView.value = false;
  allPhotosView.value = false;
  recentView.value = false;
  videosView.value = false;
  placesView.value = false;
  albumOverviewView.value = false;
  mediaFilter.value = 'all';
  currentRating.value = normalizedRating;
  ratingFilter.value = normalizedRating;
  try {
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadRatings');
  } finally {
    loading.value = false;
  }
}

async function openCameraView(camera: AssetCamera) {
  loading.value = true;
  error.value = '';
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  currentFolder.value = null;
  childFolders.value = [];
  currentTag.value = null;
  currentRating.value = null;
  currentAlbum.value = null;
  currentPlace.value = null;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  favoritesView.value = false;
  allPhotosView.value = false;
  recentView.value = false;
  videosView.value = false;
  placesView.value = false;
  albumOverviewView.value = false;
  mediaFilter.value = 'all';
  ratingFilter.value = 0;
  currentLens.value = null;
  currentCamera.value = camera;
  try {
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadCameras');
  } finally {
    loading.value = false;
  }
}

async function openLensView(lens: AssetLens) {
  loading.value = true;
  error.value = '';
  search.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  currentFolder.value = null;
  childFolders.value = [];
  currentTag.value = null;
  currentRating.value = null;
  currentAlbum.value = null;
  currentPlace.value = null;
  currentCamera.value = null;
  favoriteFilter.value = false;
  includeSubfolders.value = false;
  favoritesView.value = false;
  allPhotosView.value = false;
  recentView.value = false;
  videosView.value = false;
  placesView.value = false;
  albumOverviewView.value = false;
  mediaFilter.value = 'all';
  ratingFilter.value = 0;
  currentLens.value = lens;
  try {
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadLenses');
  } finally {
    loading.value = false;
  }
}

function openContextMenu(event: MouseEvent, folder: FolderType) {
  contextMenuFolder.value = folder;
  contextMenuPos.value = { x: event.clientX, y: event.clientY };
}

function closeContextMenu() {
  contextMenuFolder.value = null;
}

async function openCoverPicker(folder: FolderType) {
  closeContextMenu();
  coverPickerFolder.value = folder;
  coverPickerLoading.value = true;
  coverPickerAssets.value = [];
  try {
    coverPickerAssets.value = await api.assets(folder.id, '', true);
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableLoadPhotos'));
    coverPickerFolder.value = null;
  } finally {
    coverPickerLoading.value = false;
  }
}

async function selectCover(assetId: number) {
  if (!coverPickerFolder.value) return;
  const folder = coverPickerFolder.value;
  try {
    const updated = await api.updateFolderCover(folder.id, assetId);
    folder.cover_asset_id = updated.cover_asset_id;
    const idx = childFolders.value.findIndex((f) => f.id === folder.id);
    if (idx !== -1) childFolders.value[idx] = updated;
    showToast(t('album.coverUpdated'));
    coverPickerFolder.value = null;
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateCover'));
  }
}

function closeCoverPicker() {
  coverPickerFolder.value = null;
}

async function toggleFavoriteFilter() {
  favoriteFilter.value = !favoriteFilter.value;
  viewerIndex.value = null;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  if (currentFolder.value) {
    await loadAssets({ showSearchLoading: true });
  }
}

async function toggleIncludeSubfolders() {
  if (!currentFolder.value) return;
  includeSubfolders.value = !includeSubfolders.value;
  viewerIndex.value = null;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  await loadAssets({ showSearchLoading: true });
}

async function toggleAssetFavorite(asset: Asset) {
  try {
    const updated = await api.updateAssetFavorite(asset.id, !asset.is_favorite);
    updateAssetState(updated);
    if (favoritesOnlyActive.value && !updated.is_favorite) {
      assets.value = assets.value.filter((item) => item.id !== updated.id);
      selectedAssetIds.value.delete(updated.id);
      selectedAssetIds.value = new Set(selectedAssetIds.value);
      if (viewerIndex.value !== null && !displayAssets.value[viewerIndex.value]) {
        viewerIndex.value = displayAssets.value.length ? Math.max(0, displayAssets.value.length - 1) : null;
      }
    }
    showToast(updated.is_favorite ? t('album.favoriteAdded') : t('album.favoriteRemoved'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateFavorite'));
  }
}

async function toggleSelectedFavorites() {
  const selected = selectedAssets.value;
  if (!selected.length || updatingSelectionFavorite.value) return;
  const nextFavorite = selectedFavoritesTarget.value;
  updatingSelectionFavorite.value = true;
  try {
    const targets = selected.filter((asset) => asset.is_favorite !== nextFavorite);
    const updatedAssets = await Promise.all(targets.map((asset) => api.updateAssetFavorite(asset.id, nextFavorite)));
    updatedAssets.forEach(updateAssetState);
    if (!nextFavorite && favoritesOnlyActive.value) {
      const removedIds = new Set(updatedAssets.map((asset) => asset.id));
      assets.value = assets.value.filter((asset) => !removedIds.has(asset.id));
      selectedAssetIds.value = new Set([...selectedAssetIds.value].filter((id) => !removedIds.has(id)));
      if (viewerIndex.value !== null && !displayAssets.value[viewerIndex.value]) {
        viewerIndex.value = displayAssets.value.length ? Math.max(0, displayAssets.value.length - 1) : null;
      }
    }
    showToast(nextFavorite ? t('album.selectedFavoritesAdded') : t('album.selectedFavoritesRemoved'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateFavorite'));
  } finally {
    updatingSelectionFavorite.value = false;
  }
}

async function updateAssetTags(asset: Asset, tags: string[]) {
  try {
    const updated = await api.updateAssetTags(asset.id, tags);
    updateAssetState(updated);
    if (currentTag.value && !updated.tags.includes(currentTag.value)) {
      assets.value = assets.value.filter((item) => item.id !== updated.id);
      selectedAssetIds.value.delete(updated.id);
      selectedAssetIds.value = new Set(selectedAssetIds.value);
      if (viewerIndex.value !== null && !displayAssets.value[viewerIndex.value]) {
        viewerIndex.value = displayAssets.value.length ? Math.max(0, displayAssets.value.length - 1) : null;
      }
    }
    await loadTags();
    showToast(t('common.saved'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateTags'));
  }
}

async function updateAssetMetadata(asset: Asset, metadata: { description: string; rating: number }) {
  try {
    const updated = await api.updateAssetMetadata(asset.id, {
      description: metadata.description,
      rating: metadata.rating,
    });
    updateAssetState(updated);
    if (effectiveRatingFilter.value > 0 && updated.rating < effectiveRatingFilter.value) {
      assets.value = assets.value.filter((item) => item.id !== updated.id);
      selectedAssetIds.value.delete(updated.id);
      selectedAssetIds.value = new Set(selectedAssetIds.value);
      if (viewerIndex.value !== null && !displayAssets.value[viewerIndex.value]) {
        viewerIndex.value = displayAssets.value.length ? Math.max(0, displayAssets.value.length - 1) : null;
      }
    }
    await loadRatings();
    showToast(t('common.saved'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateMetadata'));
  }
}

async function setAlbumCover(asset: Asset) {
  if (!currentAlbum.value) return;
  try {
    const updated = await api.updateAlbumCover(currentAlbum.value.id, asset.id);
    currentAlbum.value = updated;
    photoAlbums.value = photoAlbums.value.map((album) => (album.id === updated.id ? updated : album));
    showToast(t('album.albumCoverUpdated'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateAlbumCover'));
  }
}

async function removeAssetFromAlbum(asset: Asset) {
  if (!currentAlbum.value || removingFromAlbum.value) return;
  const album = currentAlbum.value;
  const previousViewerIndex = viewerIndex.value;
  removingFromAlbum.value = true;
  try {
    const updated = await api.removeAlbumAssets(album.id, [asset.id]);
    assets.value = assets.value.filter((item) => item.id !== asset.id);
    selectedAssetIds.value.delete(asset.id);
    selectedAssetIds.value = new Set(selectedAssetIds.value);
    lastSelectedAssetIndex.value = null;
    keepViewerInsideAssets(previousViewerIndex);
    await loadAlbums();
    currentAlbum.value = photoAlbums.value.find((item) => item.id === updated.id) ?? updated;
    showToast(t('album.removedFromAlbum'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableRemoveFromAlbum'));
  } finally {
    removingFromAlbum.value = false;
  }
}

function keepViewerInsideAssets(previousIndex: number | null) {
  if (previousIndex === null) return;
  viewerIndex.value = displayAssets.value.length ? Math.min(previousIndex, displayAssets.value.length - 1) : null;
}

function updateAssetState(updated: Asset) {
  assets.value = assets.value.map((asset) => (asset.id === updated.id ? updated : asset));
  coverPickerAssets.value = coverPickerAssets.value.map((asset) => (asset.id === updated.id ? updated : asset));
}

function openRenameModal(folder: FolderType) {
  closeContextMenu();
  renameFolder.value = folder;
  renameName.value = folder.name;
  nextTick(() => {
    renameInputRef.value?.focus();
    renameInputRef.value?.select();
  });
}

function closeRenameModal() {
  renameFolder.value = null;
  renameName.value = '';
}

async function confirmRename() {
  const name = renameName.value.trim();
  if (!name || !renameFolder.value) return;
  const folder = renameFolder.value;
  try {
    const updated = await api.renameFolder(folder.id, name);
    folder.name = updated.name;
    const idx = childFolders.value.findIndex((f) => f.id === folder.id);
    if (idx !== -1) childFolders.value[idx] = updated;
    showToast(t('album.folderRenamed'));
    renameFolder.value = null;
    renameName.value = '';
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableRenameFolder'));
  }
}

function toggleSelectionMode() {
  selectionMode.value = !selectionMode.value;
  if (!selectionMode.value) {
    selectedAssetIds.value = new Set();
    lastSelectedAssetIndex.value = null;
  }
}

function toggleAssetSelection(assetId: number, assetIndex: number, event?: MouseEvent) {
  const next = new Set(selectedAssetIds.value);
  if (event?.shiftKey && lastSelectedAssetIndex.value !== null) {
    const [start, end] = [lastSelectedAssetIndex.value, assetIndex].sort((a, b) => a - b);
    displayAssets.value.slice(start, end + 1).forEach((asset) => next.add(asset.id));
    selectedAssetIds.value = next;
    return;
  }
  if (next.has(assetId)) {
    next.delete(assetId);
  } else {
    next.add(assetId);
  }
  selectedAssetIds.value = next;
  lastSelectedAssetIndex.value = assetIndex;
}

function clearSelection() {
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
}

function selectAllVisibleAssets() {
  selectedAssetIds.value = new Set(displayAssets.value.map((asset) => asset.id));
  lastSelectedAssetIndex.value = displayAssets.value.length ? displayAssets.value.length - 1 : null;
}

async function openPlace(place: PlaceCluster) {
  loading.value = true;
  error.value = '';
  cancelSearchTimer();
  searchLoading.value = false;
  currentPlace.value = place;
  mobileTree.value = false;
  viewerIndex.value = null;
  selectionMode.value = false;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  try {
    await loadAssets();
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('album.unableLoadPlaces');
  } finally {
    loading.value = false;
  }
}

async function setMediaFilter(value: MediaFilter) {
  if (videosView.value && value === 'video') return;
  if (!videosView.value && mediaFilter.value === value) return;
  mediaFilter.value = value;
  viewerIndex.value = null;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  if (videosView.value) {
    await openAllPhotosView();
    return;
  }
  if (assetActionsEnabled.value || currentFolder.value) {
    await loadAssets({ showSearchLoading: true });
  }
}

async function setRatingFilter(value: number) {
  const normalizedRating = Math.min(5, Math.max(0, Math.trunc(value)));
  ratingFilter.value = currentRating.value ? Math.max(normalizedRating, currentRating.value) : normalizedRating;
  viewerIndex.value = null;
  selectedAssetIds.value = new Set();
  lastSelectedAssetIndex.value = null;
  if (assetActionsEnabled.value || currentFolder.value) {
    await loadAssets({ showSearchLoading: true });
  }
}

function isVideoAsset(asset: Asset) {
  return asset.mime_type.startsWith('video/');
}

function visibleAssetTags(asset: Asset) {
  return asset.tags.slice(0, 3);
}

function shareSelectedAssets() {
  const ids = Array.from(selectedAssetIds.value);
  if (!ids.length) return;
  shareCreateTarget.value = { asset_ids: ids };
  shareCreateTitle.value = '';
  shareCreateExpiry.value = 7;
}

function openBulkTagModal() {
  if (!selectedAssetIds.value.size) return;
  bulkTagInput.value = '';
  bulkTagOpen.value = true;
  nextTick(() => {
    bulkTagInputRef.value?.focus();
  });
}

function closeBulkTagModal() {
  if (addingSelectionTags.value) return;
  bulkTagOpen.value = false;
  bulkTagInput.value = '';
}

async function confirmBulkTags() {
  const ids = Array.from(selectedAssetIds.value);
  const tags = bulkTagPreview.value;
  if (!ids.length || !tags.length || addingSelectionTags.value) return;
  addingSelectionTags.value = true;
  try {
    const updatedAssets = await api.addAssetTags(ids, tags);
    updatedAssets.forEach(updateAssetState);
    await loadTags();
    bulkTagOpen.value = false;
    bulkTagInput.value = '';
    if (selectionMode.value) toggleSelectionMode();
    showToast(t('album.tagsAddedToSelection'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateTags'));
  } finally {
    addingSelectionTags.value = false;
  }
}

function openRemoveTagModal() {
  if (!selectedAssetIds.value.size) return;
  removeTagInput.value = currentTag.value ?? '';
  removeTagOpen.value = true;
  nextTick(() => {
    removeTagInputRef.value?.focus();
    if (!currentTag.value) removeTagInputRef.value?.select();
  });
}

function closeRemoveTagModal() {
  if (removingSelectionTags.value) return;
  removeTagOpen.value = false;
  removeTagInput.value = '';
}

async function confirmRemoveTags() {
  const ids = Array.from(selectedAssetIds.value);
  const tags = removeTagPreview.value;
  if (!ids.length || !tags.length || removingSelectionTags.value) return;
  removingSelectionTags.value = true;
  try {
    const updatedAssets = await api.removeAssetTags(ids, tags);
    updatedAssets.forEach(updateAssetState);
    if (currentTag.value && tags.some((tag) => tag.toLocaleLowerCase() === currentTag.value?.toLocaleLowerCase())) {
      const removedIds = new Set(updatedAssets.map((asset) => asset.id));
      assets.value = assets.value.filter((asset) => !removedIds.has(asset.id));
    }
    selectedAssetIds.value = new Set();
    lastSelectedAssetIndex.value = null;
    await loadTags();
    removeTagOpen.value = false;
    removeTagInput.value = '';
    showToast(t('album.tagsRemovedFromSelection'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateTags'));
  } finally {
    removingSelectionTags.value = false;
  }
}

function openRenameTag(tag: AssetTag) {
  renameTagTarget.value = tag;
  renameTagName.value = tag.name;
  nextTick(() => {
    renameTagInputRef.value?.focus();
    renameTagInputRef.value?.select();
  });
}

function closeRenameTag() {
  if (renamingTag.value) return;
  renameTagTarget.value = null;
  renameTagName.value = '';
}

async function confirmRenameTag() {
  const tag = renameTagTarget.value;
  const name = renameTagName.value.trim().replace(/\s+/g, ' ');
  if (!tag || !name || renamingTag.value) return;
  renamingTag.value = true;
  try {
    const updated = await api.renameAssetTag(tag.name, name);
    if (currentTag.value === tag.name) {
      currentTag.value = updated.name;
      await loadAssets({ showSearchLoading: true });
    }
    await loadTags();
    showToast(t('album.tagRenamed'));
    renameTagTarget.value = null;
    renameTagName.value = '';
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableRenameTag'));
  } finally {
    renamingTag.value = false;
  }
}

function openDeleteTag(tag: AssetTag) {
  deleteTagTarget.value = tag;
}

function closeDeleteTag() {
  if (deletingTag.value) return;
  deleteTagTarget.value = null;
}

async function confirmDeleteTag() {
  const tag = deleteTagTarget.value;
  if (!tag || deletingTag.value) return;
  deletingTag.value = true;
  try {
    await api.deleteAssetTag(tag.name);
    deleteTagTarget.value = null;
    await loadTags();
    if (currentTag.value === tag.name) {
      await openAllPhotosView();
    } else {
      assets.value = assets.value.map((asset) => ({
        ...asset,
        tags: asset.tags.filter((name) => name !== tag.name),
      }));
    }
    showToast(t('album.tagDeleted'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableDeleteTag'));
  } finally {
    deletingTag.value = false;
  }
}

async function openCreateAlbumModal() {
  await openCreateAlbumModalForAssets(Array.from(selectedAssetIds.value), 'selection');
}

function openNewAlbumModal() {
  if (creatingNewAlbum.value) return;
  newAlbumName.value = '';
  newAlbumDescription.value = '';
  newAlbumOpen.value = true;
  nextTick(() => {
    newAlbumNameInputRef.value?.focus();
  });
}

function closeNewAlbumModal() {
  if (creatingNewAlbum.value) return;
  resetNewAlbumModal();
}

function resetNewAlbumModal() {
  newAlbumOpen.value = false;
  newAlbumName.value = '';
  newAlbumDescription.value = '';
}

async function confirmNewAlbum() {
  const name = newAlbumName.value.trim();
  if (!name || creatingNewAlbum.value) return;
  creatingNewAlbum.value = true;
  try {
    const album = await api.createAlbum({
      name,
      description: newAlbumDescription.value.trim(),
    });
    await loadAlbums();
    resetNewAlbumModal();
    showToast(t('album.albumCreated'));
    await openAlbumView(photoAlbums.value.find((item) => item.id === album.id) ?? album);
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableCreateAlbum'));
  } finally {
    creatingNewAlbum.value = false;
  }
}

async function openCreateAlbumForAsset(asset: Asset) {
  await openCreateAlbumModalForAssets([asset.id], 'viewer');
}

async function openCreateAlbumModalForAssets(assetIds: number[], source: 'selection' | 'viewer') {
  if (!assetIds.length || creatingAlbum.value) return;
  createAlbumAssetIds.value = [...new Set(assetIds)];
  createAlbumSource.value = source;
  createAlbumName.value = '';
  albumTargetFilter.value = '';
  selectedTargetAlbumId.value = photoAlbums.value[0]?.id ?? null;
  createAlbumOpen.value = true;
  await loadAlbums();
  selectedTargetAlbumId.value = photoAlbums.value[0]?.id ?? null;
  if (!photoAlbums.value.length) nextTick(() => albumNameInputRef.value?.focus());
}

function closeCreateAlbumModal() {
  if (creatingAlbum.value) return;
  resetCreateAlbumModal();
}

function resetCreateAlbumModal() {
  createAlbumOpen.value = false;
  createAlbumName.value = '';
  createAlbumAssetIds.value = [];
  createAlbumSource.value = null;
  albumTargetFilter.value = '';
  selectedTargetAlbumId.value = null;
}

function selectTargetAlbum(albumId: number) {
  selectedTargetAlbumId.value = albumId;
  createAlbumName.value = '';
}

async function confirmCreateAlbum() {
  const name = createAlbumName.value.trim();
  const assetIds = createAlbumAssetIds.value;
  const targetAlbumId = selectedTargetAlbumId.value;
  if ((!targetAlbumId && !name) || !assetIds.length || creatingAlbum.value) return;
  const source = createAlbumSource.value;
  creatingAlbum.value = true;
  try {
    const album = targetAlbumId
      ? await api.addAlbumAssets(targetAlbumId, assetIds)
      : await api.createAlbum({ name, asset_ids: assetIds });
    await loadAlbums();
    resetCreateAlbumModal();
    if (source === 'selection' && selectionMode.value) toggleSelectionMode();
    showToast(targetAlbumId ? t('album.albumUpdated') : t('album.albumCreated'));
    if (source === 'selection') {
      await openAlbumView(photoAlbums.value.find((item) => item.id === album.id) ?? album);
    }
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateAlbum'));
  } finally {
    creatingAlbum.value = false;
  }
}

async function openAlbumAssetPicker() {
  if (!currentAlbum.value || addingAlbumPickerAssets.value) return;
  if (selectionMode.value) {
    selectionMode.value = false;
    clearSelection();
  }
  resetAlbumAssetPickerState();
  albumAssetPickerOpen.value = true;
  nextTick(() => {
    albumAssetPickerSearchInputRef.value?.focus();
  });
  await loadAlbumAssetPickerCandidates({ refreshExisting: true });
}

function closeAlbumAssetPicker() {
  if (addingAlbumPickerAssets.value) return;
  albumAssetPickerOpen.value = false;
  resetAlbumAssetPickerState();
}

function resetAlbumAssetPickerState() {
  cancelAlbumAssetPickerSearchTimer();
  albumAssetPickerRequestId += 1;
  albumAssetPickerSearch.value = '';
  albumAssetPickerCandidates.value = [];
  albumAssetPickerExistingIds.value = new Set();
  albumAssetPickerSelectedIds.value = new Set();
  albumAssetPickerLoading.value = false;
  albumAssetPickerError.value = '';
}

async function loadAlbumAssetPickerCandidates({ refreshExisting = false }: { refreshExisting?: boolean } = {}) {
  const album = currentAlbum.value;
  if (!album) return;
  const requestId = ++albumAssetPickerRequestId;
  albumAssetPickerLoading.value = true;
  albumAssetPickerError.value = '';
  try {
    if (refreshExisting) {
      const existingAssets = await api.albumAssets(album.id);
      if (requestId !== albumAssetPickerRequestId) return;
      albumAssetPickerExistingIds.value = new Set(existingAssets.map((asset) => asset.id));
    }
    const candidates = await api.assets(null, albumAssetPickerSearchQuery.value, false, false, {
      sort: 'recent',
      limit: 200,
    });
    if (requestId !== albumAssetPickerRequestId) return;
    const existingIds = albumAssetPickerExistingIds.value;
    albumAssetPickerCandidates.value = candidates.filter((asset) => !existingIds.has(asset.id));
  } catch (err) {
    if (requestId === albumAssetPickerRequestId) {
      albumAssetPickerError.value = err instanceof Error ? err.message : t('album.unableLoadPhotos');
    }
  } finally {
    if (requestId === albumAssetPickerRequestId) {
      albumAssetPickerLoading.value = false;
    }
  }
}

function queueAlbumAssetPickerSearch() {
  cancelAlbumAssetPickerSearchTimer();
  albumAssetPickerRequestId += 1;
  albumAssetPickerLoading.value = true;
  albumAssetPickerSearchTimer = window.setTimeout(() => {
    loadAlbumAssetPickerCandidates();
  }, 280);
}

function clearAlbumAssetPickerSearch() {
  if (!albumAssetPickerSearch.value) return;
  albumAssetPickerSearch.value = '';
  cancelAlbumAssetPickerSearchTimer();
  loadAlbumAssetPickerCandidates();
}

function cancelAlbumAssetPickerSearchTimer() {
  if (albumAssetPickerSearchTimer) {
    window.clearTimeout(albumAssetPickerSearchTimer);
    albumAssetPickerSearchTimer = null;
  }
}

function toggleAlbumPickerAsset(assetId: number) {
  const next = new Set(albumAssetPickerSelectedIds.value);
  if (next.has(assetId)) {
    next.delete(assetId);
  } else {
    next.add(assetId);
  }
  albumAssetPickerSelectedIds.value = next;
}

function selectAllAlbumPickerVisible() {
  const next = new Set(albumAssetPickerSelectedIds.value);
  albumAssetPickerCandidates.value.forEach((asset) => next.add(asset.id));
  albumAssetPickerSelectedIds.value = next;
}

function clearAlbumAssetPickerSelection() {
  albumAssetPickerSelectedIds.value = new Set();
}

async function confirmAlbumAssetPicker() {
  const album = currentAlbum.value;
  const assetIds = Array.from(albumAssetPickerSelectedIds.value);
  if (!album || !assetIds.length || addingAlbumPickerAssets.value) return;
  addingAlbumPickerAssets.value = true;
  try {
    const updated = await api.addAlbumAssets(album.id, assetIds);
    await loadAlbums();
    currentAlbum.value = photoAlbums.value.find((item) => item.id === updated.id) ?? updated;
    albumAssetPickerOpen.value = false;
    resetAlbumAssetPickerState();
    await loadAssets({ showSearchLoading: true });
    showToast(t('album.albumUpdated'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateAlbum'));
  } finally {
    addingAlbumPickerAssets.value = false;
  }
}

async function removeSelectedFromAlbum() {
  if (!currentAlbum.value || !selectedAssetIds.value.size || removingFromAlbum.value) return;
  const album = currentAlbum.value;
  const ids = Array.from(selectedAssetIds.value);
  const previousViewerIndex = viewerIndex.value;
  removingFromAlbum.value = true;
  try {
    const updated = await api.removeAlbumAssets(album.id, ids);
    assets.value = assets.value.filter((asset) => !selectedAssetIds.value.has(asset.id));
    selectedAssetIds.value = new Set();
    lastSelectedAssetIndex.value = null;
    keepViewerInsideAssets(previousViewerIndex);
    await loadAlbums();
    currentAlbum.value = photoAlbums.value.find((item) => item.id === updated.id) ?? updated;
    showToast(t('album.removedFromAlbum'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableRemoveFromAlbum'));
  } finally {
    removingFromAlbum.value = false;
  }
}

function openDeleteAlbum() {
  if (!currentAlbum.value) return;
  deleteAlbumTarget.value = currentAlbum.value;
}

function openEditAlbum() {
  if (!currentAlbum.value) return;
  editAlbumTarget.value = currentAlbum.value;
  editAlbumName.value = currentAlbum.value.name;
  editAlbumDescription.value = currentAlbum.value.description;
  nextTick(() => {
    editAlbumNameInputRef.value?.focus();
    editAlbumNameInputRef.value?.select();
  });
}

function closeEditAlbum() {
  if (savingAlbum.value) return;
  editAlbumTarget.value = null;
  editAlbumName.value = '';
  editAlbumDescription.value = '';
}

async function confirmEditAlbum() {
  const album = editAlbumTarget.value;
  const name = editAlbumName.value.trim();
  if (!album || !name || savingAlbum.value) return;
  savingAlbum.value = true;
  try {
    const updated = await api.updateAlbum(album.id, {
      name,
      description: editAlbumDescription.value.trim(),
    });
    currentAlbum.value = updated;
    photoAlbums.value = photoAlbums.value.map((item) => (item.id === updated.id ? updated : item));
    await loadAlbums();
    showToast(t('album.albumUpdated'));
    closeEditAlbum();
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateAlbum'));
  } finally {
    savingAlbum.value = false;
  }
}

function closeDeleteAlbum() {
  if (deletingAlbum.value) return;
  deleteAlbumTarget.value = null;
}

async function confirmDeleteAlbum() {
  const album = deleteAlbumTarget.value;
  if (!album || deletingAlbum.value) return;
  deletingAlbum.value = true;
  try {
    await api.deleteAlbum(album.id);
    showToast(t('album.albumDeleted'));
    deleteAlbumTarget.value = null;
    currentAlbum.value = null;
    selectionMode.value = false;
    selectedAssetIds.value = new Set();
    lastSelectedAssetIndex.value = null;
    await loadAlbums();
    goRoot();
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableDeleteAlbum'));
  } finally {
    deletingAlbum.value = false;
  }
}

async function downloadSelectedAssets() {
  const ids = Array.from(selectedAssetIds.value);
  if (!ids.length || downloadingSelection.value) return;
  downloadingSelection.value = true;
  try {
    const archive = await api.downloadAssets(ids);
    triggerBrowserDownload(archive, 'dk-photo-originals.zip');
    showToast(t('album.downloadSelectedStarted'));
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableDownloadSelected'));
  } finally {
    downloadingSelection.value = false;
  }
}

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function normalizeTagInput(value: string) {
  const seen = new Set<string>();
  const tags: string[] = [];
  for (const rawTag of value.split(/[,，\n]/)) {
    const tag = rawTag.trim().replace(/\s+/g, ' ').slice(0, 40);
    const key = tag.toLocaleLowerCase();
    if (!tag || seen.has(key)) continue;
    tags.push(tag);
    seen.add(key);
    if (tags.length >= 30) break;
  }
  return tags;
}

function handleAlbumKeydown(event: KeyboardEvent) {
  if (viewerIndex.value !== null || isTypingTarget(event.target)) return;
  if (event.key === 'Escape' && selectionMode.value) {
    selectionMode.value = false;
    clearSelection();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a' && assetActionsEnabled.value && displayAssets.value.length) {
    event.preventDefault();
    if (!selectionMode.value) selectionMode.value = true;
    selectAllVisibleAssets();
  }
}

function isTypingTarget(target: EventTarget | null) {
  const element = target as HTMLElement | null;
  if (!element) return false;
  const tagName = element.tagName.toLowerCase();
  return tagName === 'input' || tagName === 'textarea' || tagName === 'select' || element.isContentEditable;
}

function closeShareCreate() {
  shareCreateTarget.value = null;
  shareCreateTitle.value = '';
  shareCreateExpiry.value = 7;
  shareCreatePassword.value = undefined;
}

async function confirmCreateShare() {
  const target = shareCreateTarget.value;
  if (!target) return;
  try {
    const payload: Record<string, unknown> = { title: shareCreateTitle.value };
    if (target.asset_id) payload.asset_id = target.asset_id;
    if (target.folder_id) payload.folder_id = target.folder_id;
    if (target.asset_ids) payload.asset_ids = target.asset_ids;
    if (shareCreateExpiry.value > 0) {
      payload.expires_in_days = shareCreateExpiry.value;
    } else {
      payload.expires_in_days = 0;
    }
    if (shareCreatePassword.value) {
      payload.password = shareCreatePassword.value;
    }
    const share = await api.createShare(
      payload as { title?: string; asset_id?: number; folder_id?: number; asset_ids?: number[]; expires_in_days?: number; password?: string },
    );
    await navigator.clipboard?.writeText(`${location.origin}/share/${share.token}`);
    showToast(t('album.shareCopied'));
    closeShareCreate();
    if (selectionMode.value) toggleSelectionMode();
    if (showSharesPanel.value) await loadMyShares();
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableCreateShare'));
  }
}

function toggleSection(name: string) {
  collapsedSections.value = {
    ...collapsedSections.value,
    [name]: !collapsedSections.value[name],
  };
}

async function toggleSharesPanel() {
  showSharesPanel.value = !showSharesPanel.value;
  if (showSharesPanel.value) await loadMyShares();
}

async function loadMyShares() {
  sharesLoading.value = true;
  try {
    myShares.value = await api.myShares();
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableLoadShares'));
  } finally {
    sharesLoading.value = false;
  }
}

async function copyMyShareLink(share: ShareLink) {
  try {
    await navigator.clipboard?.writeText(`${location.origin}/share/${share.token}`);
    showToast(t('admin.shareCopied'));
  } catch {
    showToast(t('admin.unableCopyShare'));
  }
}

function shareScopeLabel(share: ShareLink) {
  if (share.share_kind === 'asset') return t('album.shareSingleAsset');
  if (share.share_kind === 'folder') return t('album.shareFolder');
  return t('album.shareAssetCount', { count: formatCount(share.asset_count, 'media') });
}

function shareSearchText(share: ShareLink) {
  return `${share.title} ${share.token} ${shareScopeLabel(share)} ${shareStatusLabel(share)} ${shareExpiryLabel(share)}`.toLowerCase();
}

function shareMatchesStatus(share: ShareLink) {
  if (shareStatusFilter.value === 'all') return true;
  if (shareStatusFilter.value === 'active') return !isShareExpired(share);
  if (shareStatusFilter.value === 'never') return !share.expires_at;
  if (shareStatusFilter.value === 'expired') return isShareExpired(share);
  return isShareExpiringSoon(share);
}

function shareStatusLabel(share: ShareLink) {
  if (isShareExpired(share)) return t('admin.shareStatusExpired');
  if (isShareExpiringSoon(share)) return t('album.shareStatusExpiring');
  if (!share.expires_at) return t('album.shareStatusNever');
  return t('admin.shareStatusActive');
}

function shareStatusClass(share: ShareLink) {
  if (isShareExpired(share)) return 'off';
  if (isShareExpiringSoon(share)) return 'active';
  return 'neutral';
}

function shareExpiryLabel(share: ShareLink) {
  return share.expires_at ? t('album.shareExpires', { date: formatDate(share.expires_at) }) : t('album.shareNeverExpires');
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
    const updated = await api.updateShare(share.id, payload);
    const idx = myShares.value.findIndex((s) => s.id === share.id);
    if (idx !== -1) myShares.value[idx] = updated;
    showToast(t('album.shareUpdated'));
    closeEditShare();
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableUpdateShare'));
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
    await api.deleteShare(share.id);
    myShares.value = myShares.value.filter((s) => s.id !== share.id);
    showToast(t('album.shareDeleted'));
    closeDeleteShare();
  } catch (err) {
    showToast(err instanceof Error ? err.message : t('album.unableDeleteShare'));
  }
}

function setThumbSize(value: ThumbSize) {
  thumbSize.value = value;
}

function setSortMode(value: SortMode) {
  sortMode.value = value;
  viewerIndex.value = null;
}

function toggleSortDirection() {
  sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc';
  viewerIndex.value = null;
}

function setAlbumSortMode(value: AlbumSortMode) {
  albumSortMode.value = value;
}

function toggleAlbumSortDirection() {
  albumSortDirection.value = albumSortDirection.value === 'asc' ? 'desc' : 'asc';
}

function retryCurrentView() {
  if (currentAlbum.value) {
    openAlbumView(currentAlbum.value);
  } else if (albumOverviewView.value) {
    openAlbumOverviewView();
  } else if (recentView.value) {
    openRecentView();
  } else if (videosView.value) {
    openVideosView();
  } else if (placesView.value) {
    openPlacesView();
  } else if (currentTag.value) {
    openTagView(currentTag.value);
  } else if (currentRating.value) {
    openRatingView(currentRating.value);
  } else if (currentCamera.value) {
    openCameraView(currentCamera.value);
  } else if (currentLens.value) {
    openLensView(currentLens.value);
  } else if (allPhotosView.value) {
    openAllPhotosView();
  } else if (favoritesView.value) {
    openFavoritesView();
  } else if (currentFolder.value) {
    openFolder(currentFolder.value);
  } else if (globalSearchActive.value) {
    loadAssets({ showSearchLoading: true });
  } else {
    loadRoot();
  }
}

function showToast(message: string) {
  toastMessage.value = message;
  if (toastTimer) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toastMessage.value = '';
  }, 3200);
}

function storedThumbSize(): ThumbSize {
  const value = localStorage.getItem('dk-photo-thumb-size');
  return value === 'small' || value === 'medium' || value === 'large' ? value : 'medium';
}

function storedMediaFilter(): MediaFilter {
  const value = localStorage.getItem('dk-photo-media-filter');
  return value === 'image' || value === 'video' ? value : 'all';
}

function storedSortMode(): SortMode {
  const value = localStorage.getItem('dk-photo-sort-mode');
  return value === 'date' || value === 'name' || value === 'size' ? value : 'date';
}

function storedSortDirection(): SortDirection {
  const value = localStorage.getItem('dk-photo-sort-direction');
  return value === 'asc' || value === 'desc' ? value : 'desc';
}

function storedAlbumSortMode(): AlbumSortMode {
  const value = localStorage.getItem('dk-photo-album-sort-mode');
  return value === 'updated' || value === 'name' || value === 'count' ? value : 'updated';
}

function storedAlbumSortDirection(): SortDirection {
  const value = localStorage.getItem('dk-photo-album-sort-direction');
  return value === 'asc' || value === 'desc' ? value : 'desc';
}

function compareByDirection(value: number) {
  return sortDirection.value === 'asc' ? value : -value;
}

function sortPhotoAlbums(albums: PhotoAlbum[]) {
  return [...albums].sort((a, b) => {
    let value: number;
    if (albumSortMode.value === 'name') {
      value = a.name.localeCompare(b.name);
    } else if (albumSortMode.value === 'count') {
      value = a.asset_count - b.asset_count;
    } else {
      value = Date.parse(a.updated_at || a.created_at) - Date.parse(b.updated_at || b.created_at);
    }
    return albumSortDirection.value === 'asc' ? value : -value;
  });
}

function sortPlaceClusters(places: PlaceCluster[]) {
  return [...places].sort((a, b) => {
    let value: number;
    if (sortMode.value === 'name') {
      value = a.label.localeCompare(b.label);
    } else if (sortMode.value === 'size') {
      value = a.assetCount - b.assetCount;
    } else {
      value = a.latestAt - b.latestAt;
    }
    return compareByDirection(value);
  });
}

function placeFromApi(place: AssetPlace): PlaceCluster {
  return {
    key: place.place_key,
    label: place.label,
    latitude: place.latitude,
    longitude: place.longitude,
    assetCount: place.asset_count,
    coverAssetId: place.cover_asset_id,
    latestAt: Date.parse(place.latest_at || '') || 0,
  };
}

function placeCoordinateLabel(place: PlaceCluster) {
  return `${place.latitude.toFixed(5)}, ${place.longitude.toFixed(5)}`;
}

function placeMapUrl(place: PlaceCluster) {
  return `https://www.google.com/maps?q=${place.latitude},${place.longitude}`;
}

function assetDateLabel(asset: Asset) {
  const raw = asset.captured_at || asset.updated_at;
  return formatDate(raw);
}

function albumUpdatedDateLabel(album: PhotoAlbum) {
  return formatDate(album.updated_at || album.created_at);
}

function ratingLabel(rating: number) {
  return rating > 0 ? t('viewer.ratingValue', { rating }) : t('viewer.unrated');
}

function assetSourceLabel(asset: Asset) {
  const libraryName = asset.library_name?.trim();
  const folderPath = asset.folder_path?.trim();
  const folderName = asset.folder_name?.trim();
  const parts = [libraryName, folderPath || (folderName && folderName !== libraryName ? folderName : '')].filter(Boolean);
  return parts.join(' / ');
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
</script>
