import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, originalUrl, publicOriginalUrl, publicShareDownloadUrl, publicThumbnailUrl, thumbnailUrl } from './api';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('api url helpers', () => {
  it('builds authenticated asset urls', () => {
    expect(thumbnailUrl(42, 'small')).toBe('/api/assets/42/thumbnail?size=small');
    expect(originalUrl(42)).toBe('/api/assets/42/original');
  });

  it('builds public share asset urls', () => {
    expect(publicThumbnailUrl('token', 7, 'large')).toBe('/api/public/shares/token/assets/7/thumbnail?size=large');
    expect(publicOriginalUrl('token', 7)).toBe('/api/public/shares/token/assets/7/original');
    expect(publicShareDownloadUrl('token')).toBe('/api/public/shares/token/download');
  });

  it('builds filtered asset list query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assets(12, 'lake', true, true);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assets?folder_id=12&search=lake&recursive=true&favorites_only=true',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('builds recent asset list query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assets(null, '', false, false, { sort: 'recent', limit: 120 });

    expect(fetchMock).toHaveBeenCalledWith('/api/assets?sort=recent&limit=120', expect.objectContaining({ credentials: 'include' }));
  });

  it('builds media type asset list query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assets(null, '', false, false, { mediaType: 'video' });

    expect(fetchMock).toHaveBeenCalledWith('/api/assets?media_type=video', expect.objectContaining({ credentials: 'include' }));
  });

  it('builds location asset list query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assets(null, 'park', false, false, { mediaType: 'image', hasLocation: true });

    expect(fetchMock).toHaveBeenCalledWith('/api/assets?search=park&media_type=image&has_location=true', expect.objectContaining({ credentials: 'include' }));
  });

  it('builds tagged asset list query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assets(null, '', false, false, { tag: 'Travel' });

    expect(fetchMock).toHaveBeenCalledWith('/api/assets?tag=Travel', expect.objectContaining({ credentials: 'include' }));
  });

  it('builds rating asset list query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assets(null, 'keeper', false, false, { minRating: 3 });

    expect(fetchMock).toHaveBeenCalledWith('/api/assets?search=keeper&min_rating=3', expect.objectContaining({ credentials: 'include' }));
  });

  it('builds camera asset list query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assets(null, '', false, false, { camera: 'Canon|EOS R6' });

    expect(fetchMock).toHaveBeenCalledWith('/api/assets?camera=Canon%7CEOS+R6', expect.objectContaining({ credentials: 'include' }));
  });

  it('builds lens asset list query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assets(null, '', false, false, { lens: 'RF 24-70mm' });

    expect(fetchMock).toHaveBeenCalledWith('/api/assets?lens=RF+24-70mm', expect.objectContaining({ credentials: 'include' }));
  });

  it('builds place asset list query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assets(null, '', false, false, { place: '37.81,-122.40' });

    expect(fetchMock).toHaveBeenCalledWith('/api/assets?place=37.81%2C-122.40', expect.objectContaining({ credentials: 'include' }));
  });

  it('loads available asset tags', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ name: 'Family', asset_count: 2 }],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assetTags();

    expect(fetchMock).toHaveBeenCalledWith('/api/assets/tags', expect.objectContaining({ credentials: 'include' }));
  });

  it('loads available asset ratings', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ rating: 4, asset_count: 2 }],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assetRatings();

    expect(fetchMock).toHaveBeenCalledWith('/api/assets/ratings', expect.objectContaining({ credentials: 'include' }));
  });

  it('loads available asset cameras', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ camera_key: 'Canon|EOS R6', label: 'Canon EOS R6', asset_count: 2 }],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assetCameras();

    expect(fetchMock).toHaveBeenCalledWith('/api/assets/cameras', expect.objectContaining({ credentials: 'include' }));
  });

  it('loads available asset lenses', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ lens_key: 'RF 24-70mm', label: 'RF 24-70mm', asset_count: 2 }],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assetLenses();

    expect(fetchMock).toHaveBeenCalledWith('/api/assets/lenses', expect.objectContaining({ credentials: 'include' }));
  });

  it('loads available asset places', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ place_key: '37.81,-122.40', label: '37.81, -122.40', asset_count: 2 }],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.assetPlaces('mapped');

    expect(fetchMock).toHaveBeenCalledWith('/api/assets/places?search=mapped', expect.objectContaining({ credentials: 'include' }));
  });

  it('patches asset tags', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 9, tags: ['Family'] }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.updateAssetTags(9, ['Family']);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assets/9/tags',
      expect.objectContaining({
        method: 'PATCH',
        credentials: 'include',
        body: JSON.stringify({ tags: ['Family'] }),
      }),
    );
  });

  it('patches asset metadata', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 9, description: 'Keeper', rating: 4 }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.updateAssetMetadata(9, { description: 'Keeper', rating: 4 });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assets/9/metadata',
      expect.objectContaining({
        method: 'PATCH',
        credentials: 'include',
        body: JSON.stringify({ description: 'Keeper', rating: 4 }),
      }),
    );
  });

  it('posts selected asset ids when adding tags in bulk', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: 9, tags: ['Family'] }],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.addAssetTags([9, 12], ['Family']);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assets/bulk-tags',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ asset_ids: [9, 12], tags: ['Family'] }),
      }),
    );
  });

  it('posts selected asset ids when removing tags in bulk', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: 9, tags: [] }],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.removeAssetTags([9, 12], ['Family']);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assets/bulk-tags/remove',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ asset_ids: [9, 12], tags: ['Family'] }),
      }),
    );
  });

  it('renames an asset tag', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ name: 'Family Trip', asset_count: 2 }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.renameAssetTag('Family Trip', 'Holiday');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assets/tags/Family%20Trip',
      expect.objectContaining({
        method: 'PATCH',
        credentials: 'include',
        body: JSON.stringify({ name: 'Holiday' }),
      }),
    );
  });

  it('deletes an asset tag', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.deleteAssetTag('Family Trip');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assets/tags/Family%20Trip',
      expect.objectContaining({
        method: 'DELETE',
        credentials: 'include',
      }),
    );
  });

  it('posts selected asset ids for original download', async () => {
    const archive = new Blob(['zip']);
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => archive,
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(api.downloadAssets([3, 7])).resolves.toBe(archive);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/assets/download',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ asset_ids: [3, 7] }),
      }),
    );
  });

  it('downloads all public share originals', async () => {
    const archive = new Blob(['zip']);
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => archive,
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(api.downloadPublicShare('share-token')).resolves.toBe(archive);
    expect(fetchMock).toHaveBeenCalledWith('/api/public/shares/share-token/download', expect.objectContaining({ credentials: 'include' }));
  });

  it('posts selected asset ids when creating an album', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, name: 'Weekend', asset_count: 2 }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.createAlbum({ name: 'Weekend', asset_ids: [3, 7] });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/albums',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ name: 'Weekend', asset_ids: [3, 7] }),
      }),
    );
  });

  it('patches album details', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 9, name: 'Renamed', description: 'Notes' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.updateAlbum(9, { name: 'Renamed', description: 'Notes' });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/albums/9',
      expect.objectContaining({
        method: 'PATCH',
        credentials: 'include',
        body: JSON.stringify({ name: 'Renamed', description: 'Notes' }),
      }),
    );
  });

  it('patches an album cover', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 9, cover_asset_id: 42 }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.updateAlbumCover(9, 42);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/albums/9/cover',
      expect.objectContaining({
        method: 'PATCH',
        credentials: 'include',
        body: JSON.stringify({ cover_asset_id: 42 }),
      }),
    );
  });

  it('posts selected asset ids when adding to an existing album', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 9, name: 'Weekend', asset_count: 3 }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.addAlbumAssets(9, [3, 7]);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/albums/9/assets',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ asset_ids: [3, 7] }),
      }),
    );
  });

  it('sends selected asset ids when removing from an album', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 9, name: 'Weekend', asset_count: 1 }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.removeAlbumAssets(9, [3, 7]);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/albums/9/assets',
      expect.objectContaining({
        method: 'DELETE',
        credentials: 'include',
        body: JSON.stringify({ asset_ids: [3, 7] }),
      }),
    );
  });

  it('deletes an album by id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.deleteAlbum(9);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/albums/9',
      expect.objectContaining({
        method: 'DELETE',
        credentials: 'include',
      }),
    );
  });

  it('builds album asset search query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.albumAssets(9, 'beach');
    expect(fetchMock).toHaveBeenCalledWith('/api/albums/9/assets?search=beach', expect.objectContaining({ credentials: 'include' }));
  });

  it('builds album asset media type query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.albumAssets(9, 'clip', { mediaType: 'video' });
    expect(fetchMock).toHaveBeenCalledWith('/api/albums/9/assets?search=clip&media_type=video', expect.objectContaining({ credentials: 'include' }));
  });

  it('builds album asset rating query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.albumAssets(9, 'keeper', { mediaType: 'image', minRating: 4 });
    expect(fetchMock).toHaveBeenCalledWith('/api/albums/9/assets?search=keeper&media_type=image&min_rating=4', expect.objectContaining({ credentials: 'include' }));
  });

  it('loads all album assets when no search is provided', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.albumAssets(9);
    expect(fetchMock).toHaveBeenCalledWith('/api/albums/9/assets', expect.objectContaining({ credentials: 'include' }));
  });
});
