import { describe, expect, it } from 'vitest';
import { originalUrl, publicOriginalUrl, publicThumbnailUrl, thumbnailUrl } from './api';

describe('api url helpers', () => {
  it('builds authenticated asset urls', () => {
    expect(thumbnailUrl(42, 'small')).toBe('/api/assets/42/thumbnail?size=small');
    expect(originalUrl(42)).toBe('/api/assets/42/original');
  });

  it('builds public share asset urls', () => {
    expect(publicThumbnailUrl('token', 7, 'large')).toBe('/api/public/shares/token/assets/7/thumbnail?size=large');
    expect(publicOriginalUrl('token', 7)).toBe('/api/public/shares/token/assets/7/original');
  });
});
