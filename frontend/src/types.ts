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
  created_at: string;
  last_scan_at: string | null;
}

export interface LibraryUpdate {
  name?: string;
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
  mime_type: string;
  width: number | null;
  height: number | null;
  size: number;
  mtime: number;
  captured_at: string | null;
  updated_at: string;
}

export interface ScanJob {
  id: number;
  library_id: number;
  status: string;
  message: string;
  total_assets: number;
  started_at: string | null;
  finished_at: string | null;
}

export interface ShareLink {
  id: number;
  token: string;
  title: string;
  asset_id: number | null;
  folder_id: number | null;
  asset_ids: number[] | null;
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
}
