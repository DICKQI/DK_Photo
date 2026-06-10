import { describe, expect, it } from 'vitest';
import type { Library } from '../types';
import { deleteProgressLabel, deleteProgressPercent, deleteProgressPhaseLabel } from './deleteProgress';

const messages: Record<string, string> = {
  'admin.deletePhaseCounting': 'Counting media and folders',
  'admin.deletePhaseAssets': 'Deleting media',
  'admin.deletePhaseFolders': 'Deleting folders',
  'admin.deletePhaseFinalizing': 'Finalizing',
  'admin.deletePhaseFailed': 'Deletion failed',
  'admin.deleteProgressTotal': '{phase} {count} / {total} ({percent}%)',
  'admin.deleteProgressNoTotal': '{phase}',
  'admin.deleteFailedWithMessage': '{phase}: {message}',
};

function t(key: string, params?: Record<string, string | number>) {
  let message = messages[key] ?? key;
  for (const [name, value] of Object.entries(params ?? {})) {
    message = message.replace(`{${name}}`, String(value));
  }
  return message;
}

function library(overrides: Partial<Library>): Library {
  return {
    id: 1,
    name: 'Archive',
    path: '/photos/archive',
    is_enabled: false,
    watch_enabled: false,
    created_at: '2026-01-01T00:00:00Z',
    last_scan_at: null,
    deleted_at: '2026-06-10T00:00:00Z',
    delete_status: 'running',
    delete_phase: 'assets',
    delete_message: 'Deleting media index and thumbnails',
    delete_total_assets: 100,
    delete_processed_assets: 45,
    delete_total_folders: 10,
    delete_processed_folders: 0,
    delete_started_at: '2026-06-10T00:00:00Z',
    delete_updated_at: '2026-06-10T00:00:03Z',
    ...overrides,
  };
}

describe('deleteProgress helpers', () => {
  it('formats asset deletion progress with a percentage', () => {
    const item = library({});

    expect(deleteProgressPercent(item)).toBe(45);
    expect(deleteProgressPhaseLabel(item, t)).toBe('Deleting media');
    expect(deleteProgressLabel(item, t)).toBe('Deleting media 45 / 100 (45%)');
  });

  it('falls back to phase-only copy before totals are known', () => {
    const item = library({
      delete_phase: 'counting',
      delete_total_assets: 0,
      delete_processed_assets: 0,
      delete_total_folders: 0,
      delete_processed_folders: 0,
    });

    expect(deleteProgressPercent(item)).toBeNull();
    expect(deleteProgressLabel(item, t)).toBe('Counting media and folders');
  });

  it('shows failed deletion messages directly', () => {
    const item = library({
      delete_status: 'failed',
      delete_phase: 'failed',
      delete_message: 'thumbnail boom',
    });

    expect(deleteProgressPhaseLabel(item, t)).toBe('Deletion failed');
    expect(deleteProgressLabel(item, t)).toBe('Deletion failed: thumbnail boom');
  });
});
