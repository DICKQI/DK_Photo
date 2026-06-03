import { describe, expect, it } from 'vitest';
import { nextLocale, normalizeLocale, persistLocale, resolveInitialLocale, translateWithLocale, type TranslationKey } from './useLocale';

describe('useLocale helpers', () => {
  it('normalizes supported locale values', () => {
    expect(normalizeLocale('zh-CN')).toBe('zh-CN');
    expect(normalizeLocale('zh-Hans')).toBe('zh-CN');
    expect(normalizeLocale('en-US')).toBe('en');
    expect(normalizeLocale('fr-FR')).toBeNull();
  });

  it('prefers stored locale before browser languages', () => {
    expect(resolveInitialLocale('en', ['zh-CN'])).toBe('en');
    expect(resolveInitialLocale('zh-CN', ['en-US'])).toBe('zh-CN');
  });

  it('uses browser Chinese preference when there is no stored locale', () => {
    expect(resolveInitialLocale(null, ['en-US', 'zh-CN'])).toBe('zh-CN');
    expect(resolveInitialLocale(null, ['en-US'])).toBe('en');
  });

  it('toggles and persists locale values', () => {
    const writes: Record<string, string> = {};
    const storage = {
      getItem: (key: string) => writes[key] ?? null,
      setItem: (key: string, value: string) => {
        writes[key] = value;
      },
    };

    expect(nextLocale('en')).toBe('zh-CN');
    persistLocale('zh-CN', storage);
    expect(writes['dk-photo-locale']).toBe('zh-CN');
  });

  it('interpolates translated messages and marks missing keys', () => {
    expect(translateWithLocale('zh-CN', 'album.nothingMatches', { query: '猫' })).toBe('此文件夹中没有内容匹配“猫”。');
    expect(translateWithLocale('en', 'missing.key' as TranslationKey)).toBe('[missing.key]');
  });
});
