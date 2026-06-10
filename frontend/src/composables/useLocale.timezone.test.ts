import { describe, expect, it, vi } from 'vitest';
import { useLocale } from './useLocale';

describe('useLocale timezone formatting', () => {
  it('formats dates in UTC+8', () => {
    const api = useLocale();
    api.setLocale('en');

    const dateSpy = vi.spyOn(Date.prototype, 'toLocaleDateString');
    const timeSpy = vi.spyOn(Date.prototype, 'toLocaleString');

    try {
      api.formatDate('2024-05-12T02:30:45Z');
      api.formatDateTime('2024-05-12T02:30:45Z');

      expect(dateSpy).toHaveBeenCalledWith('en', expect.objectContaining({ timeZone: 'Asia/Shanghai' }));
      expect(timeSpy).toHaveBeenCalledWith('en', expect.objectContaining({ timeZone: 'Asia/Shanghai' }));
    } finally {
      dateSpy.mockRestore();
      timeSpy.mockRestore();
    }
  });
});
