import type {
  Asset,
  AssetCamera,
  AssetLens,
  AssetPlace,
  AssetRating,
  AssetTag,
  FilesystemChildren,
  FilesystemRoots,
  Folder,
  Library,
  LibraryUpdate,
  LibraryPermission,
  PhotoAlbum,
  PublicShare,
  ScanJob,
  ShareLink,
  User,
} from '../types';

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(detail.detail || response.statusText);
  }
  return response.json() as Promise<T>;
}

async function downloadRequest(url: string, init: RequestInit = {}): Promise<Blob> {
  const response = await fetch(url, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(detail.detail || response.statusText);
  }
  return response.blob();
}

export async function downloadUrl(url: string): Promise<Blob> {
  return downloadRequest(url);
}

export const api = {
  login(email: string, password: string) {
    return request<User>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },
  logout() {
    return request<{ ok: boolean }>('/api/auth/logout', { method: 'POST' });
  },
  me() {
    return request<User>('/api/auth/me');
  },
  libraries() {
    return request<Library[]>('/api/admin/libraries');
  },
  createLibrary(name: string, path: string) {
    return request<Library>('/api/admin/libraries', {
      method: 'POST',
      body: JSON.stringify({ name, path }),
    });
  },
  updateLibrary(libraryId: number, payload: LibraryUpdate) {
    return request<Library>(`/api/admin/libraries/${libraryId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  deleteLibrary(libraryId: number) {
    return request<{ ok: boolean }>(`/api/admin/libraries/${libraryId}`, { method: 'DELETE' });
  },
  scanLibrary(libraryId: number) {
    return request<ScanJob>(`/api/admin/libraries/${libraryId}/scan`, { method: 'POST' });
  },
  cancelScanJob(jobId: number) {
    return request<{ ok: boolean }>(`/api/admin/jobs/${jobId}/cancel`, { method: 'POST' });
  },
  jobs() {
    return request<ScanJob[]>('/api/admin/jobs');
  },
  users() {
    return request<User[]>('/api/admin/users');
  },
  createUser(email: string, displayName: string, password: string, role: string) {
    return request<User>('/api/admin/users', {
      method: 'POST',
      body: JSON.stringify({ email, display_name: displayName, password, role }),
    });
  },
  updateUser(id: number, payload: { email?: string; display_name?: string; role?: string }) {
    return request<User>(`/api/admin/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  resetUserPassword(id: number, password: string) {
    return request<{ ok: boolean }>(`/api/admin/users/${id}/password`, {
      method: 'POST',
      body: JSON.stringify({ password }),
    });
  },
  disableUser(id: number) {
    return request<User>(`/api/admin/users/${id}/disable`, { method: 'POST' });
  },
  enableUser(id: number) {
    return request<User>(`/api/admin/users/${id}/enable`, { method: 'POST' });
  },
  deleteUser(id: number) {
    return request<{ ok: boolean }>(`/api/admin/users/${id}`, { method: 'DELETE' });
  },
  userPermissions(id: number) {
    return request<LibraryPermission[]>(`/api/admin/users/${id}/permissions`);
  },
  updateUserPermissions(id: number, payload: Array<{ library_id: number; can_view: boolean; can_share: boolean }>) {
    return request<LibraryPermission[]>(`/api/admin/users/${id}/permissions`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  filesystemRoots() {
    return request<FilesystemRoots>('/api/admin/filesystem/roots');
  },
  filesystemChildren(path: string) {
    return request<FilesystemChildren>(`/api/admin/filesystem/children?path=${encodeURIComponent(path)}`);
  },
  adminShares() {
    return request<ShareLink[]>('/api/admin/shares');
  },
  updateAdminShare(id: number, payload: { title?: string; expires_in_days?: number; password?: string }) {
    return request<ShareLink>(`/api/admin/shares/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  deleteAdminShare(id: number) {
    return request<{ ok: boolean }>(`/api/admin/shares/${id}`, { method: 'DELETE' });
  },
  folders(parentId: number | null = null, libraryId?: number) {
    const params = new URLSearchParams();
    if (parentId !== null) params.set('parent_id', String(parentId));
    if (libraryId) params.set('library_id', String(libraryId));
    const suffix = params.toString() ? `?${params}` : '';
    return request<Folder[]>(`/api/folders${suffix}`);
  },
  folder(id: number) {
    return request<Folder>(`/api/folders/${id}`);
  },
  updateFolderCover(folderId: number, coverAssetId: number) {
    return request<Folder>(`/api/folders/${folderId}/cover`, {
      method: 'PATCH',
      body: JSON.stringify({ cover_asset_id: coverAssetId }),
    });
  },
  renameFolder(folderId: number, name: string) {
    return request<Folder>(`/api/folders/${folderId}/rename`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    });
  },
  assets(
    folderId: number | null,
    search = '',
    recursive = false,
    favoritesOnly = false,
    options: { sort?: 'name' | 'recent'; limit?: number; offset?: number; mediaType?: 'all' | 'image' | 'video'; hasLocation?: boolean; tag?: string; minRating?: number; camera?: string; lens?: string; place?: string } = {},
  ) {
    const params = new URLSearchParams();
    if (folderId !== null) params.set('folder_id', String(folderId));
    if (search) params.set('search', search);
    if (recursive) params.set('recursive', 'true');
    if (favoritesOnly) params.set('favorites_only', 'true');
    if (options.sort) params.set('sort', options.sort);
    if (options.limit) params.set('limit', String(options.limit));
    if (options.offset) params.set('offset', String(options.offset));
    if (options.mediaType && options.mediaType !== 'all') params.set('media_type', options.mediaType);
    if (options.hasLocation) params.set('has_location', 'true');
    if (options.tag) params.set('tag', options.tag);
    if (options.minRating) params.set('min_rating', String(options.minRating));
    if (options.camera) params.set('camera', options.camera);
    if (options.lens) params.set('lens', options.lens);
    if (options.place) params.set('place', options.place);
    const suffix = params.toString() ? `?${params}` : '';
    return request<Asset[]>(`/api/assets${suffix}`);
  },
  asset(id: number) {
    return request<Asset>(`/api/assets/${id}`);
  },
  assetTags() {
    return request<AssetTag[]>('/api/assets/tags');
  },
  assetRatings() {
    return request<AssetRating[]>('/api/assets/ratings');
  },
  assetCameras() {
    return request<AssetCamera[]>('/api/assets/cameras');
  },
  assetLenses() {
    return request<AssetLens[]>('/api/assets/lenses');
  },
  assetPlaces(search = '') {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    const suffix = params.toString() ? `?${params}` : '';
    return request<AssetPlace[]>(`/api/assets/places${suffix}`);
  },
  updateAssetFavorite(id: number, isFavorite: boolean) {
    return request<Asset>(`/api/assets/${id}/favorite`, {
      method: 'PATCH',
      body: JSON.stringify({ is_favorite: isFavorite }),
    });
  },
  updateAssetTags(id: number, tags: string[]) {
    return request<Asset>(`/api/assets/${id}/tags`, {
      method: 'PATCH',
      body: JSON.stringify({ tags }),
    });
  },
  updateAssetMetadata(id: number, payload: { description: string; rating: number }) {
    return request<Asset>(`/api/assets/${id}/metadata`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  addAssetTags(assetIds: number[], tags: string[]) {
    return request<Asset[]>('/api/assets/bulk-tags', {
      method: 'POST',
      body: JSON.stringify({ asset_ids: assetIds, tags }),
    });
  },
  removeAssetTags(assetIds: number[], tags: string[]) {
    return request<Asset[]>('/api/assets/bulk-tags/remove', {
      method: 'POST',
      body: JSON.stringify({ asset_ids: assetIds, tags }),
    });
  },
  renameAssetTag(name: string, nextName: string) {
    return request<AssetTag>(`/api/assets/tags/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      body: JSON.stringify({ name: nextName }),
    });
  },
  deleteAssetTag(name: string) {
    return request<{ ok: boolean }>(`/api/assets/tags/${encodeURIComponent(name)}`, { method: 'DELETE' });
  },
  albums() {
    return request<PhotoAlbum[]>('/api/albums');
  },
  createAlbum(payload: { name: string; description?: string; asset_ids?: number[] }) {
    return request<PhotoAlbum>('/api/albums', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  updateAlbum(albumId: number, payload: { name?: string; description?: string }) {
    return request<PhotoAlbum>(`/api/albums/${albumId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  updateAlbumCover(albumId: number, coverAssetId: number) {
    return request<PhotoAlbum>(`/api/albums/${albumId}/cover`, {
      method: 'PATCH',
      body: JSON.stringify({ cover_asset_id: coverAssetId }),
    });
  },
  addAlbumAssets(albumId: number, assetIds: number[]) {
    return request<PhotoAlbum>(`/api/albums/${albumId}/assets`, {
      method: 'POST',
      body: JSON.stringify({ asset_ids: assetIds }),
    });
  },
  removeAlbumAssets(albumId: number, assetIds: number[]) {
    return request<PhotoAlbum>(`/api/albums/${albumId}/assets`, {
      method: 'DELETE',
      body: JSON.stringify({ asset_ids: assetIds }),
    });
  },
  deleteAlbum(albumId: number) {
    return request<{ ok: boolean }>(`/api/albums/${albumId}`, { method: 'DELETE' });
  },
  albumAssets(albumId: number, search = '', options: { mediaType?: 'all' | 'image' | 'video'; minRating?: number } = {}) {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (options.mediaType && options.mediaType !== 'all') params.set('media_type', options.mediaType);
    if (options.minRating) params.set('min_rating', String(options.minRating));
    const suffix = params.toString() ? `?${params}` : '';
    return request<Asset[]>(`/api/albums/${albumId}/assets${suffix}`);
  },
  downloadAssets(assetIds: number[]) {
    return downloadRequest('/api/assets/download', {
      method: 'POST',
      body: JSON.stringify({ asset_ids: assetIds }),
    });
  },
  createShare(payload: { title?: string; asset_id?: number; folder_id?: number; asset_ids?: number[]; expires_in_days?: number; password?: string }) {
    return request<ShareLink>('/api/shares', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  myShares() {
    return request<ShareLink[]>('/api/shares');
  },
  deleteShare(id: number) {
    return request<{ ok: boolean }>(`/api/shares/${id}`, { method: 'DELETE' });
  },
  updateShare(id: number, payload: { title?: string; expires_in_days?: number; password?: string }) {
    return request<ShareLink>(`/api/shares/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  publicShare(token: string) {
    return request<PublicShare>(`/api/public/shares/${token}`);
  },
  verifySharePassword(token: string, password: string) {
    return request<{ verified: boolean; access_token: string | null }>(`/api/public/shares/${token}/verify`, {
      method: 'POST',
      body: JSON.stringify({ password }),
    });
  },
  publicShareAssets(token: string) {
    return request<Asset[]>(`/api/public/shares/${token}/assets`);
  },
  downloadPublicShare(token: string) {
    return downloadRequest(publicShareDownloadUrl(token));
  },
};

export function thumbnailUrl(assetId: number, size = 'medium') {
  return `/api/assets/${assetId}/thumbnail?size=${size}`;
}

export function originalUrl(assetId: number) {
  return `/api/assets/${assetId}/original`;
}

export function publicThumbnailUrl(token: string, assetId: number, size = 'medium') {
  return `/api/public/shares/${token}/assets/${assetId}/thumbnail?size=${size}`;
}

export function publicOriginalUrl(token: string, assetId: number) {
  return `/api/public/shares/${token}/assets/${assetId}/original`;
}

export function publicShareDownloadUrl(token: string) {
  return `/api/public/shares/${token}/download`;
}
