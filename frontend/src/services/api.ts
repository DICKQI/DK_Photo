import type {
  Asset,
  FilesystemChildren,
  FilesystemRoots,
  Folder,
  Library,
  LibraryPermission,
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
  scanLibrary(libraryId: number) {
    return request<ScanJob>(`/api/admin/libraries/${libraryId}/scan`, { method: 'POST' });
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
  assets(folderId: number | null, search = '') {
    const params = new URLSearchParams();
    if (folderId !== null) params.set('folder_id', String(folderId));
    if (search) params.set('search', search);
    const suffix = params.toString() ? `?${params}` : '';
    return request<Asset[]>(`/api/assets${suffix}`);
  },
  asset(id: number) {
    return request<Asset>(`/api/assets/${id}`);
  },
  createShare(payload: { title?: string; asset_id?: number; folder_id?: number; expires_in_days?: number }) {
    return request<ShareLink>('/api/shares', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  publicShare(token: string) {
    return request<PublicShare>(`/api/public/shares/${token}`);
  },
  publicShareAssets(token: string) {
    return request<Asset[]>(`/api/public/shares/${token}/assets`);
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
