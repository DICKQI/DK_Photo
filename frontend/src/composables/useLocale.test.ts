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

  it('exposes media and video viewer copy', () => {
    expect(translateWithLocale('en', 'common.mediaItemsUnit')).toBe('media items');
    expect(translateWithLocale('en', 'album.loadingPhotos')).toBe('Loading media');
    expect(translateWithLocale('en', 'album.noAlbumsMatch', { query: 'trip' })).toBe('No albums match "trip"');
    expect(translateWithLocale('en', 'album.sortAlbumsByCount')).toBe('Sort albums by media count');
    expect(translateWithLocale('en', 'album.shareAssetCount', { count: '2 media items' })).toBe('2 media items shared');
    expect(translateWithLocale('en', 'album.noSharesMatch', { query: 'holiday' })).toBe('No share links match "holiday"');
    expect(translateWithLocale('en', 'album.shareStatusExpiring')).toBe('Expiring soon');
    expect(translateWithLocale('en', 'album.clearAssetFilters')).toBe('Clear media filters');
    expect(translateWithLocale('en', 'album.ratingAtLeast', { rating: 3 })).toBe('3+ stars');
    expect(translateWithLocale('en', 'album.ratings')).toBe('Ratings');
    expect(translateWithLocale('en', 'album.searchRatedPhotos')).toBe('Search rated media');
    expect(translateWithLocale('en', 'album.noRatedPhotos')).toBe('No rated media');
    expect(translateWithLocale('en', 'album.unableLoadRatings')).toBe('Unable to load ratings');
    expect(translateWithLocale('en', 'album.cameras')).toBe('Cameras');
    expect(translateWithLocale('en', 'album.searchCameraPhotos')).toBe('Search camera media');
    expect(translateWithLocale('en', 'album.noCameraPhotos')).toBe('No media from this camera');
    expect(translateWithLocale('en', 'album.unableLoadCameras')).toBe('Unable to load cameras');
    expect(translateWithLocale('en', 'album.lenses')).toBe('Lenses');
    expect(translateWithLocale('en', 'album.searchLensPhotos')).toBe('Search lens media');
    expect(translateWithLocale('en', 'album.noLensPhotos')).toBe('No media from this lens');
    expect(translateWithLocale('en', 'album.unableLoadLenses')).toBe('Unable to load lenses');
    expect(translateWithLocale('en', 'admin.shareStatusExpired')).toBe('Expired');
    expect(translateWithLocale('en', 'admin.allStatuses')).toBe('All statuses');
    expect(translateWithLocale('en', 'admin.searchLibraries')).toBe('Search libraries');
    expect(translateWithLocale('en', 'admin.scanMediaProgressTotal', { count: '40,700', total: '739,497' })).toBe('Media 40,700 / 739,497');
    expect(translateWithLocale('en', 'admin.scanImageProgressTotal', { count: '39,800', total: '720,000' })).toBe('Images 39,800 / 720,000');
    expect(translateWithLocale('en', 'admin.scanThumbnailReadyImages', { count: '12,340', total: '39,800' })).toBe('Thumbnails ready 12,340 / 39,800');
    expect(translateWithLocale('en', 'admin.scanJobs')).toBe('Background Tasks');
    expect(translateWithLocale('en', 'admin.deleteProgressTotal', { phase: 'Deleting media', count: '45,000', total: '100,000', percent: 45 })).toBe('Deleting media 45,000 / 100,000 (45%)');
    expect(translateWithLocale('en', 'album.favoriteSelected')).toBe('Favorite selected');
    expect(translateWithLocale('en', 'album.addAlbumSelectionHint', { count: 2 })).toBe('2 selected media items will be added.');
    expect(translateWithLocale('en', 'share.available', { media: '2 media items' })).toBe('2 media items available from this shared link.');
    expect(translateWithLocale('en', 'share.downloadAll')).toBe('Download all');
    expect(translateWithLocale('en', 'share.noFilteredMedia')).toBe('No matching media');
    expect(translateWithLocale('en', 'viewer.loadingVideo')).toBe('Loading video');
    expect(translateWithLocale('en', 'viewer.unableDownloadOriginal')).toBe('Unable to download original');
    expect(translateWithLocale('en', 'viewer.startSlideshow')).toBe('Start slideshow');
    expect(translateWithLocale('en', 'viewer.rotateLeft')).toBe('Rotate left');
    expect(translateWithLocale('en', 'viewer.rotateRight')).toBe('Rotate right');
    expect(translateWithLocale('en', 'viewer.openMap')).toBe('Open map');
    expect(translateWithLocale('en', 'album.searchVideos')).toBe('Search videos');
    expect(translateWithLocale('en', 'album.places')).toBe('Places');
    expect(translateWithLocale('en', 'album.searchThisPlace')).toBe('Search this place');
    expect(translateWithLocale('en', 'album.placeClusterCount', { count: 2 })).toBe('2 places');
    expect(translateWithLocale('en', 'album.placeCoordinates', { coordinates: '37.81000, -122.40000' })).toBe('Coordinates 37.81000, -122.40000');
    expect(translateWithLocale('en', 'album.noLocationPhotos')).toBe('No located media');
    expect(translateWithLocale('en', 'album.unableLoadPlaces')).toBe('Unable to load places');
    expect(translateWithLocale('en', 'album.tags')).toBe('Tags');
    expect(translateWithLocale('en', 'album.searchTaggedPhotos')).toBe('Search tagged media');
    expect(translateWithLocale('en', 'album.noTagsMatch', { query: 'family' })).toBe('No tags match "family"');
    expect(translateWithLocale('en', 'album.unableUpdateTags')).toBe('Unable to update tags');
    expect(translateWithLocale('en', 'album.addTagsSelectionHint', { count: 3 })).toBe('Tags will be added to 3 selected media items.');
    expect(translateWithLocale('en', 'album.tagsAddedToSelection')).toBe('Tags added to selected media');
    expect(translateWithLocale('en', 'album.removeTagsSelectionHint', { count: 3 })).toBe('Tags will be removed from 3 selected media items.');
    expect(translateWithLocale('en', 'album.removeFromCurrentTag')).toBe('Remove from this tag');
    expect(translateWithLocale('en', 'album.renameTag')).toBe('Rename tag');
    expect(translateWithLocale('en', 'album.confirmDeleteTag', { name: 'Travel' })).toBe('Delete "Travel"? It will be removed from matching media.');
    expect(translateWithLocale('en', 'viewer.ratingValue', { rating: 4 })).toBe('4 stars');
    expect(translateWithLocale('en', 'viewer.noDescription')).toBe('No description');
    expect(translateWithLocale('en', 'viewer.tagsPlaceholder')).toBe('Family, travel, receipts...');
    expect(translateWithLocale('en', 'directory.emptyWithMedia', { media: '2 media items' })).toBe('This folder contains 2 media items and can be used as a library.');
    expect(translateWithLocale('zh-CN', 'album.videos')).toBe('视频');
    expect(translateWithLocale('zh-CN', 'album.places')).toBe('地点');
    expect(translateWithLocale('zh-CN', 'album.searchPlaces')).toBe('搜索地点');
    expect(translateWithLocale('zh-CN', 'album.searchThisPlace')).toBe('搜索此地点');
    expect(translateWithLocale('zh-CN', 'album.placeClusterCount', { count: 2 })).toBe('2 个地点');
    expect(translateWithLocale('zh-CN', 'album.placeCoordinates', { coordinates: '37.81000, -122.40000' })).toBe('坐标 37.81000, -122.40000');
    expect(translateWithLocale('zh-CN', 'album.noLocationPhotos')).toBe('还没有带地点的媒体');
    expect(translateWithLocale('zh-CN', 'album.tags')).toBe('标签');
    expect(translateWithLocale('zh-CN', 'album.searchTaggedPhotos')).toBe('搜索标签媒体');
    expect(translateWithLocale('zh-CN', 'album.noTagsMatch', { query: '家人' })).toBe('没有标签匹配“家人”');
    expect(translateWithLocale('zh-CN', 'album.unableUpdateTags')).toBe('无法更新标签');
    expect(translateWithLocale('zh-CN', 'album.addTagsSelectionHint', { count: 3 })).toBe('将为 3 个已选媒体添加这些标签。');
    expect(translateWithLocale('zh-CN', 'album.tagsAddedToSelection')).toBe('已为所选媒体添加标签');
    expect(translateWithLocale('zh-CN', 'album.removeTagsSelectionHint', { count: 3 })).toBe('将从 3 个已选媒体移除这些标签。');
    expect(translateWithLocale('zh-CN', 'album.removeFromCurrentTag')).toBe('从此标签移除');
    expect(translateWithLocale('zh-CN', 'album.renameTag')).toBe('重命名标签');
    expect(translateWithLocale('zh-CN', 'album.confirmDeleteTag', { name: '旅行' })).toBe('删除“旅行”？它会从匹配的媒体中移除。');
    expect(translateWithLocale('zh-CN', 'viewer.tagsPlaceholder')).toBe('家人、旅行、票据...');
    expect(translateWithLocale('zh-CN', 'album.filterAlbums')).toBe('筛选相册');
    expect(translateWithLocale('zh-CN', 'album.sortAlbums')).toBe('相册排序');
    expect(translateWithLocale('zh-CN', 'album.clearAssetFilters')).toBe('清除媒体筛选');
    expect(translateWithLocale('zh-CN', 'album.ratingAtLeast', { rating: 3 })).toBe('3 星及以上');
    expect(translateWithLocale('zh-CN', 'album.filterTargetAlbums')).toBe('查找相册');
    expect(translateWithLocale('zh-CN', 'album.shareFolder')).toBe('文件夹分享');
    expect(translateWithLocale('zh-CN', 'album.shareStatusNever')).toBe('永久有效');
    expect(translateWithLocale('zh-CN', 'album.selectedFavoritesRemoved')).toBe('已从收藏移除所选媒体');
    expect(translateWithLocale('zh-CN', 'admin.searchShares')).toBe('搜索分享链接');
    expect(translateWithLocale('zh-CN', 'admin.allShareStatuses')).toBe('全部状态');
    expect(translateWithLocale('zh-CN', 'admin.noMatchingLibraries')).toBe('没有匹配的图库');
    expect(translateWithLocale('zh-CN', 'admin.noMatchingScanJobs')).toBe('没有匹配的后台任务');
    expect(translateWithLocale('zh-CN', 'admin.scanMediaProgressTotal', { count: '40,700', total: '739,497' })).toBe('媒体 40,700 / 739,497');
    expect(translateWithLocale('zh-CN', 'admin.deletePhaseAssets')).toBe('正在清理媒体');
    expect(translateWithLocale('zh-CN', 'admin.scanImageProgressTotal', { count: '39,800', total: '720,000' })).toBe('已发现图片 39,800 / 720,000');
    expect(translateWithLocale('zh-CN', 'admin.scanThumbnailReadyImages', { count: '12,340', total: '39,800' })).toBe('缩略图已就绪 12,340 / 39,800');
    expect(translateWithLocale('zh-CN', 'album.noPhotosHere')).toBe('这里还没有媒体');
    expect(translateWithLocale('zh-CN', 'share.sharedPhotos')).toBe('分享媒体');
    expect(translateWithLocale('zh-CN', 'share.unableDownloadAll')).toBe('无法下载此分享');
    expect(translateWithLocale('zh-CN', 'share.noFilteredMediaHint')).toBe('试试其他媒体类型筛选。');
    expect(translateWithLocale('zh-CN', 'viewer.type')).toBe('类型');
    expect(translateWithLocale('zh-CN', 'viewer.ratingValue', { rating: 4 })).toBe('4 星');
    expect(translateWithLocale('zh-CN', 'viewer.noDescription')).toBe('无描述');
    expect(translateWithLocale('zh-CN', 'viewer.downloadStarted')).toBe('已开始下载');
    expect(translateWithLocale('zh-CN', 'viewer.pauseSlideshow')).toBe('暂停幻灯片播放');
    expect(translateWithLocale('zh-CN', 'viewer.rotateLeft')).toBe('向左旋转');
    expect(translateWithLocale('zh-CN', 'viewer.rotateRight')).toBe('向右旋转');
  });
});
