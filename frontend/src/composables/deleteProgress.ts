import type { Library } from '../types';
import type { TranslationKey } from './useLocale';

type DeleteProgressTranslator = (key: TranslationKey, params?: Record<string, string | number>) => string;

export function deleteProgressPercent(library: Library): number | null {
  if (library.delete_total_assets > 0) {
    return Math.min(100, Math.floor((library.delete_processed_assets / library.delete_total_assets) * 100));
  }
  if (library.delete_total_folders > 0) {
    return Math.min(100, Math.floor((library.delete_processed_folders / library.delete_total_folders) * 100));
  }
  return null;
}

export function deleteProgressPhaseLabel(library: Library, t: DeleteProgressTranslator): string {
  if (library.delete_status === 'failed' || library.delete_phase === 'failed') return t('admin.deletePhaseFailed');
  if (library.delete_phase === 'assets') return t('admin.deletePhaseAssets');
  if (library.delete_phase === 'folders') return t('admin.deletePhaseFolders');
  if (library.delete_phase === 'finalizing') return t('admin.deletePhaseFinalizing');
  return t('admin.deletePhaseCounting');
}

export function deleteProgressLabel(library: Library, t: DeleteProgressTranslator): string {
  const phase = deleteProgressPhaseLabel(library, t);
  if (library.delete_status === 'failed') {
    return t('admin.deleteFailedWithMessage', { phase, message: library.delete_message || phase });
  }
  const percent = deleteProgressPercent(library);
  const count = library.delete_total_assets > 0 ? library.delete_processed_assets : library.delete_processed_folders;
  const total = library.delete_total_assets > 0 ? library.delete_total_assets : library.delete_total_folders;
  if (percent === null || total <= 0) {
    return t('admin.deleteProgressNoTotal', { phase });
  }
  return t('admin.deleteProgressTotal', {
    phase,
    count: count.toLocaleString(),
    total: total.toLocaleString(),
    percent,
  });
}
