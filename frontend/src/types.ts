export interface User {
  id: number;
  email: string;
  display_name: string;
  role: 'admin' | 'member';
  is_active: boolean;
}

export interface Library {
  id: number;
  name: string;
  path: string;
  is_enabled: boolean;
  watch_enabled: boolean;
  created_at: string;
  last_scan_at: string | null;
  deleted_at: string | null;
}

export interface LibraryUpdate {
  name?: string;
  watch_enabled?: boolean;
}

export interface Folder {
  id: number;
  library_id: number;
  parent_id: number | null;
  path: string;
  name: string;
  photo_count: number;
  folder_count: number;
  cover_asset_id: number | null;
  updated_at: string;
  ancestors?: Folder[];
}

export interface Asset {
  id: number;
  library_id: number;
  folder_id: number;
  filename: string;
  path: string;
  library_name: string | null;
  folder_name: string | null;
  folder_path: string | null;
  mime_type: string;
  width: number | null;
  height: number | null;
  size: number;
  mtime: number;
  captured_at: string | null;
  camera_make: string | null;
  camera_model: string | null;
  lens_model: string | null;
  iso: number | null;
  aperture: string | null;
  exposure_time: string | null;
  focal_length: string | null;
  latitude: number | null;
  longitude: number | null;
  tags: string[];
  description: string;
  rating: number;
  updated_at: string;
  is_favorite: boolean;
}

export interface AssetTag {
  name: string;
  asset_count: number;
}

export interface AssetRating {
  rating: number;
  asset_count: number;
}

export interface AssetCamera {
  camera_key: string;
  label: string;
  asset_count: number;
}

export interface AssetLens {
  lens_key: string;
  label: string;
  asset_count: number;
}

export interface AssetPlace {
  place_key: string;
  label: string;
  latitude: number;
  longitude: number;
  asset_count: number;
  cover_asset_id: number | null;
  latest_at: string | null;
}

export interface PhotoAlbum {
  id: number;
  name: string;
  description: string;
  asset_count: number;
  cover_asset_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ScanJob {
  id: number;
  library_id: number;
  status: string;
  message: string;
  total_assets: number;
  total_estimated: number | null;
  processed_assets: number;
  started_at: string | null;
  finished_at: string | null;
  library_name?: string | null;
}

export interface ThumbnailStats {
  total_count: number;
  total_size_bytes: number;
  small_count: number;
  medium_count: number;
  large_count: number;
}

export interface ThumbnailCleanupResult {
  deleted_files: number;
  freed_bytes: number;
  deleted_dirs: number;
}

export interface ServerSettings {
  thumb_workers: number;
  cpu_count: number | null;
  thumb_workers_default: number;
}

export interface ShareLink {
  id: number;
  token: string;
  title: string;
  asset_id: number | null;
  folder_id: number | null;
  asset_ids: number[] | null;
  asset_count: number;
  share_kind: 'asset' | 'folder' | 'assets';
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface PublicShare {
  token: string;
  title: string;
  asset_id: number | null;
  folder_id: number | null;
  asset_ids: number[] | null;
  expires_at: string | null;
  has_password: boolean;
}

export interface LibraryPermission {
  user_id: number;
  library_id: number;
  can_view: boolean;
  can_share: boolean;
}

export interface FilesystemEntry {
  name: string;
  path: string;
  is_root: boolean;
  is_accessible: boolean;
  error: string | null;
  kind: 'folder' | 'favorite' | 'drive' | 'error';
  group: string | null;
  child_folder_count: number;
  image_count: number;
  media_count?: number;
}

export interface FilesystemRoots {
  platform: string;
  separator: string;
  roots: FilesystemEntry[];
}

export interface FilesystemChildren {
  platform: string;
  separator: string;
  path: string;
  parent_path: string | null;
  entries: FilesystemEntry[];
  child_folder_count: number;
  image_count: number;
  media_count?: number;
}
