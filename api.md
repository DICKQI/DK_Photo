# DK Photo API 文档

## 概述

- **基础路径**：所有接口以 `/api` 开头
- **认证方式**：JWT Token，通过 HTTP-only Cookie (`dk_photo_token`) 传递，有效期 7 天
- **Content-Type**：`application/json`（文件下载和缩略图除外）
- **角色**：`admin`（管理员）、`member`（成员）。管理员可访问所有接口和所有图库

---

## 1. 认证接口

### POST /api/auth/login

登录并设置认证 Cookie。

**请求体**
```json
{
  "email": "admin@example.com",
  "password": "change-me-now"
}
```

**响应** `200`
```json
{
  "id": 1,
  "email": "admin@example.com",
  "display_name": "Admin",
  "role": "admin",
  "is_active": true
}
```

**错误**
| 状态码 | 说明 |
| --- | --- |
| 401 | 邮箱或密码错误 |
| 403 | 用户已被禁用 |

---

### GET /api/auth/me

获取当前登录用户信息。需要认证。

**响应** `200`
```json
{
  "id": 1,
  "email": "admin@example.com",
  "display_name": "Admin",
  "role": "admin",
  "is_active": true
}
```

---

### POST /api/auth/logout

退出登录，清除认证 Cookie。

**响应** `200`
```json
{ "ok": true }
```

---

## 2. 文件夹接口

### GET /api/folders

列出文件夹。需要认证。

**查询参数**
| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `parent_id` | int | 否 | 父文件夹 ID，为空则列出根文件夹 |
| `library_id` | int | 否 | 限定图库 |

**响应** `200` — 数组
```json
[
  {
    "id": 1,
    "library_id": 1,
    "parent_id": null,
    "path": "/photos",
    "name": "Family Photos",
    "photo_count": 42,
    "folder_count": 3,
    "cover_asset_id": 100,
    "updated_at": "2025-01-15T12:00:00"
  }
]
```

---

### GET /api/folders/{folder_id}

获取文件夹详情（含祖先链）。需要认证。

**响应** `200`
```json
{
  "id": 5,
  "library_id": 1,
  "parent_id": 1,
  "path": "/photos/2024",
  "name": "2024",
  "photo_count": 20,
  "folder_count": 0,
  "cover_asset_id": null,
  "updated_at": "2025-01-15T12:00:00",
  "ancestors": [
    {
      "id": 1,
      "library_id": 1,
      "parent_id": null,
      "path": "/photos",
      "name": "Family Photos",
      "photo_count": 42,
      "folder_count": 3,
      "cover_asset_id": 100,
      "updated_at": "2025-01-15T12:00:00"
    }
  ]
}
```

**错误**
| 状态码 | 说明 |
| --- | --- |
| 404 | 文件夹不存在 |

---

### PATCH /api/folders/{folder_id}/cover

更改文件夹封面。需要管理员角色。

**请求体**
```json
{
  "cover_asset_id": 123
}
```

**响应** `200` — 参见 [FolderRead](#folderread)

**错误**
| 状态码 | 说明 |
| --- | --- |
| 404 | 文件夹或资源不存在 |
| 400 | 资源不属于此文件夹 |

---

### PATCH /api/folders/{folder_id}/rename

重命名文件夹。需要管理员角色。

**请求体**
```json
{
  "name": "New Folder Name"
}
```

**响应** `200` — 参见 [FolderRead](#folderread)

**错误**
| 状态码 | 说明 |
| --- | --- |
| 404 | 文件夹不存在 |
| 422 | 名称为空 |

---

## 3. 资源接口

### GET /api/assets

列出/搜索/筛选资源。需要认证。

**查询参数**
| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `folder_id` | int | — | 限定文件夹 |
| `recursive` | bool | false | 是否递归包含子文件夹 |
| `search` | string | — | 搜索关键词（匹配文件名、路径、相机、镜头、标签、描述等） |
| `sort` | enum | `name` | 排序：`name`（按文件名）/ `recent`（按创建时间倒序） |
| `limit` | int | — | 返回数量上限（1-500） |
| `media_type` | enum | `all` | `all` / `image` / `video` |
| `favorites_only` | bool | false | 仅显示收藏 |
| `has_location` | bool | false | 仅显示有 GPS 坐标的资源 |
| `tag` | string | — | 按标签筛选（精确匹配） |
| `min_rating` | int | 0 | 最低评分（1-5），0 表示不筛选 |
| `camera` | string | — | 按相机筛选（格式 `Make|Model`） |
| `lens` | string | — | 按镜头筛选（精确匹配镜头名称） |
| `place` | string | — | 按地点筛选（格式 `lat,lon`） |

**响应** `200` — 数组，参见 [AssetRead](#assetread)

**示例**
```
GET /api/assets?folder_id=1&recursive=true&sort=recent&media_type=image&min_rating=3&limit=50
```

---

### GET /api/assets/tags

列出当前用户所有标签及其数量。需要认证。

**响应** `200` — 数组
```json
[
  { "name": "family", "asset_count": 15 },
  { "name": "travel", "asset_count": 8 },
  { "name": "vacation", "asset_count": 3 }
]
```

---

### GET /api/assets/ratings

列出评分分布（1-5 星，各星级数量为累积值）。需要认证。

**响应** `200` — 数组
```json
[
  { "rating": 1, "asset_count": 25 },
  { "rating": 2, "asset_count": 18 },
  { "rating": 3, "asset_count": 12 },
  { "rating": 4, "asset_count": 7 },
  { "rating": 5, "asset_count": 3 }
]
```

> 说明：`asset_count` 是累积值。例如 `rating: 3` 的数量表示评分 ≥ 3 的所有资源。

---

### GET /api/assets/cameras

列出所有相机型号及数量（按数量降序排列）。需要认证。

**响应** `200` — 数组
```json
[
  {
    "camera_key": "Canon|EOS R5",
    "label": "Canon EOS R5",
    "asset_count": 120
  },
  {
    "camera_key": "Apple|iPhone 15 Pro",
    "label": "Apple iPhone 15 Pro",
    "asset_count": 85
  }
]
```

---

### GET /api/assets/lenses

列出所有镜头型号及数量（按数量降序排列）。需要认证。

**响应** `200` — 数组
```json
[
  {
    "lens_key": "EF24-70mm f/2.8L II USM",
    "label": "EF24-70mm f/2.8L II USM",
    "asset_count": 56
  }
]
```

---

### GET /api/assets/places

列出 GPS 地点聚类（精确到小数点后两位）。需要认证。

**查询参数**
| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `search` | string | 搜索关键词 |

**响应** `200` — 数组
```json
[
  {
    "place_key": "39.90,116.40",
    "label": "39.90, 116.40",
    "latitude": 39.90,
    "longitude": 116.40,
    "asset_count": 15,
    "cover_asset_id": 200,
    "latest_at": "2025-01-15T12:00:00"
  }
]
```

---

### POST /api/assets/bulk-tags

批量添加标签。需要认证。

**请求体**
```json
{
  "asset_ids": [1, 2, 3],
  "tags": ["vacation", "family"]
}
```
| 字段 | 约束 |
| --- | --- |
| `asset_ids` | 必填，最少 1 个，最多 500 个 |
| `tags` | 最多 30 个，每个标签最长 40 字符 |

**响应** `200` — 数组，参见 [AssetRead](#assetread)

---

### POST /api/assets/bulk-tags/remove

批量移除标签。需要认证。

**请求体** — 格式同 `bulk-tags`

**响应** `200` — 数组，参见 [AssetRead](#assetread)

---

### PATCH /api/assets/tags/{tag_name}

重命名标签。需要认证。
> 注意：`{tag_name}` 是原始标签名称（URL 编码），不是 ID。

**请求体**
```json
{
  "name": "new-tag-name"
}
```
| 字段 | 约束 |
| --- | --- |
| `name` | 必填，1-40 字符 |

**响应** `200`
```json
{
  "name": "new-tag-name",
  "asset_count": 10
}
```

**错误**
| 状态码 | 说明 |
| --- | --- |
| 404 | 标签不存在 |

---

### DELETE /api/assets/tags/{tag_name}

删除标签（删除当前用户所有使用此标签的记录）。需要认证。

**响应** `200`
```json
{ "ok": true }
```

---

### GET /api/assets/{asset_id}

获取单个资源详情。需要认证。

**响应** `200` — 参见 [AssetRead](#assetread)

**错误**
| 状态码 | 说明 |
| --- | --- |
| 404 | 资源不存在 |

---

### PATCH /api/assets/{asset_id}/favorite

切换收藏状态。需要认证。

**请求体**
```json
{ "is_favorite": true }
```

**响应** `200` — 参见 [AssetRead](#assetread)

---

### PATCH /api/assets/{asset_id}/metadata

更新描述和评分。需要认证。

**请求体**
```json
{
  "description": "一张美丽的日落照片",
  "rating": 4
}
```
| 字段 | 约束 |
| --- | --- |
| `description` | 最长 2000 字符 |
| `rating` | 0-5 整数（0 表示不评分） |

**响应** `200` — 参见 [AssetRead](#assetread)

> 说明：当 `description` 为空且 `rating` 为 0 时，会删除已有的元数据记录。

---

### PATCH /api/assets/{asset_id}/tags

替换全部标签（覆盖模式）。需要认证。

**请求体**
```json
{
  "tags": ["sunset", "beach", "favorite"]
}
```
| 字段 | 约束 |
| --- | --- |
| `tags` | 最多 30 个，每个标签最长 40 字符 |

**响应** `200` — 参见 [AssetRead](#assetread)

---

### POST /api/assets/download

批量下载原文件为 ZIP。需要认证。

**请求体**
```json
{
  "asset_ids": [1, 2, 3]
}
```
| 字段 | 约束 |
| --- | --- |
| `asset_ids` | 最少 1 个，最多 500 个 |

**响应** `200` — `application/zip` 文件流，Content-Disposition 为 `attachment; filename="dk-photo-originals.zip"`。

---

### GET /api/assets/{asset_id}/original

下载原始文件。需要认证。

**响应** `200` — 原始文件的二进制流，Content-Type 为实际 MIME 类型。

---

### GET /api/assets/{asset_id}/thumbnail

获取缩略图。需要认证。

**查询参数**
| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `size` | enum | `medium` | `small` (320px) / `medium` (720px) / `large` (1440px) |

**响应** `200` — `image/webp` 缩略图。

---

## 4. 相册接口

### GET /api/albums

列出当前用户的所有相册。需要认证。

**响应** `200` — 数组，参见 [AlbumRead](#albumread)

---

### POST /api/albums

创建相册，可选初始照片列表。需要认证。

**请求体**
```json
{
  "name": "我的相册",
  "description": "精选照片",
  "asset_ids": [1, 2, 3]
}
```
| 字段 | 约束 |
| --- | --- |
| `name` | 必填，1-120 字符 |
| `description` | 最长 500 字符 |
| `asset_ids` | 最多 500 个资源 ID |

**响应** `200` — 参见 [AlbumRead](#albumread)

**错误**
| 状态码 | 说明 |
| --- | --- |
| 422 | 相册名称为空 |

---

### GET /api/albums/{album_id}

获取相册详情。需要认证。

**响应** `200` — 参见 [AlbumRead](#albumread)

**错误**
| 状态码 | 说明 |
| --- | --- |
| 404 | 相册不存在或不属于当前用户 |

---

### PATCH /api/albums/{album_id}

更新相册名称和描述。需要认证。

**请求体**
```json
{
  "name": "新名称",
  "description": "新描述"
}
```
| 字段 | 约束 |
| --- | --- |
| `name` | 1-120 字符 |
| `description` | 最长 500 字符 |

**响应** `200` — 参见 [AlbumRead](#albumread)

---

### PATCH /api/albums/{album_id}/cover

设置相册封面。需要认证。

**请求体**
```json
{
  "cover_asset_id": 100
}
```

**响应** `200` — 参见 [AlbumRead](#albumread)

**错误**
| 状态码 | 说明 |
| --- | --- |
| 400 | 该资源不在相册中 |
| 404 | 资源不存在 |

---

### GET /api/albums/{album_id}/assets

列出相册内的资源。需要认证。

**查询参数**
| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `search` | string | — | 搜索关键词 |
| `media_type` | enum | `all` | `all` / `image` / `video` |
| `min_rating` | int | 0 | 最低评分 |

**响应** `200` — 数组，参见 [AssetRead](#assetread)（按添加到相册的时间排序）

---

### POST /api/albums/{album_id}/assets

添加资源到相册。需要认证。

**请求体**
```json
{
  "asset_ids": [4, 5, 6]
}
```
| 字段 | 约束 |
| --- | --- |
| `asset_ids` | 必填，最少 1 个，最多 500 个 |

**响应** `200` — 参见 [AlbumRead](#albumread)

---

### DELETE /api/albums/{album_id}/assets

从相册移除资源。需要认证。

**请求体** — 格式同添加接口

**响应** `200` — 参见 [AlbumRead](#albumread)

> 说明：如果被移除的资源是封面，封面会被自动清空。

---

### DELETE /api/albums/{album_id}

删除相册（同时删除所有关联的资源记录）。需要认证。

**响应** `200`
```json
{ "ok": true }
```

---

## 5. 分享接口

### POST /api/shares

创建分享链接。需要认证。

**请求体**

必须指定以下三者之一：

```json
// 分享单张照片
{
  "asset_id": 123,
  "title": "查看这张照片",
  "expires_in_days": 7
}

// 分享整个文件夹
{
  "folder_id": 5,
  "title": "2024年照片",
  "expires_in_days": 30
}

// 分享多张照片
{
  "asset_ids": [1, 2, 3],
  "title": "精选合集",
  "expires_in_days": 0
}
```

| 字段 | 约束 |
| --- | --- |
| `title` | 最长 160 字符 |
| `asset_id` / `folder_id` / `asset_ids` | 三者必选其一 |
| `expires_in_days` | 0-365 天，0 表示永不过期 |

**响应** `200` — 参见 [ShareRead](#shareread)

**错误**
| 状态码 | 说明 |
| --- | --- |
| 400 | 未指定或同时指定了多个分享对象 |
| 404 | 资源/文件夹不存在 |

---

### GET /api/shares

列出我创建的分享链接（仅未撤销的）。需要认证。

**响应** `200` — 数组，参见 [ShareRead](#shareread)（按创建时间倒序）

---

### PATCH /api/shares/{share_id}

更新分享链接（标题和/或过期时间）。需要认证。

**请求体**
```json
{
  "title": "新标题",
  "expires_in_days": 30
}
```
| 字段 | 说明 |
| --- | --- |
| `title` | 可选，最长 160 字符 |
| `expires_in_days` | 可选，0 清除过期时间，1-365 设定天数。从当前时间重新计算 |

**响应** `200` — 参见 [ShareRead](#shareread)

**错误**
| 状态码 | 说明 |
| --- | --- |
| 404 | 分享不存在 |
| 403 | 不是你的分享链接 |
| 400 | 分享已被撤销 |

---

### DELETE /api/shares/{share_id}

撤销分享链接（不真正删除，只是设置 revoked_at）。需要认证。

**响应** `200`
```json
{ "ok": true }
```

---

### 公开分享接口（无需认证）

以下接口通过分享 token 访问，无需登录。

---

### GET /api/public/shares/{token}

获取分享的元数据信息。

**响应** `200`
```json
{
  "token": "aBcDeFgHiJkLmNoPqRsTuVwXyZ",
  "title": "查看这张照片",
  "asset_id": 123,
  "folder_id": null,
  "asset_ids": null,
  "expires_at": "2025-02-15T12:00:00"
}
```
| 字段 | 说明 |
| --- | --- |
| `asset_id` | 单张照片分享时不为 null |
| `folder_id` | 文件夹分享时不为 null |
| `asset_ids` | 多张照片分享时为资源 ID 数组 |

**错误**
| 状态码 | 说明 |
| --- | --- |
| 404 | 分享不存在或已撤销 |
| 410 | 分享已过期 |

---

### GET /api/public/shares/{token}/assets

列出分享中包含的所有资源。

**响应** `200` — 数组，参见 [AssetRead](#assetread)

---

### GET /api/public/shares/{token}/download

下载分享中所有资源为 ZIP。

**响应** `200` — `application/zip` 文件流。

---

### GET /api/public/shares/{token}/assets/{asset_id}/original

从分享中下载原始文件。

**响应** `200` — 原始文件二进制流。

---

### GET /api/public/shares/{token}/assets/{asset_id}/thumbnail

从分享中获取缩略图。

**查询参数**
| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `size` | enum | `medium` | `small` / `medium` / `large` |

**响应** `200` — `image/webp`

---

## 6. 管理接口

所有管理接口需要 `admin` 角色。

### 图库管理

#### GET /api/admin/libraries

列出所有图库。

**响应** `200` — 数组，参见 [LibraryRead](#libraryread)

---

#### POST /api/admin/libraries

创建图库。

**请求体**
```json
{
  "name": "我的照片",
  "path": "/mnt/photos"
}
```
| 字段 | 约束 |
| --- | --- |
| `name` | 必填，1-120 字符 |
| `path` | 必填，服务器上的目录路径 |

**响应** `200` — 参见 [LibraryRead](#libraryread)

**错误**
| 状态码 | 说明 |
| --- | --- |
| 409 | 图库路径已存在 |

---

#### PATCH /api/admin/libraries/{library_id}

更新图库名称。

**请求体**
```json
{ "name": "新名称" }
```

**响应** `200` — 参见 [LibraryRead](#libraryread)

---

#### DELETE /api/admin/libraries/{library_id}

删除图库及其所有关联数据（资源、文件夹、缩略图、权限、扫描任务、分享链接等）。

**响应** `200`
```json
{ "ok": true }
```

**错误**
| 状态码 | 说明 |
| --- | --- |
| 404 | 图库不存在 |

---

#### POST /api/admin/libraries/{library_id}/scan

触发扫描任务。任务在后台异步执行。

**响应** `200` — 参见 [ScanJobRead](#scanjobread)（初始状态为 `queued`）

**错误**
| 状态码 | 说明 |
| --- | --- |
| 404 | 图库不存在 |
| 400 | 图库路径不存在 |

---

#### GET /api/admin/jobs

查看最近 40 个扫描任务。

**响应** `200` — 数组，参见 [ScanJobRead](#scanjobread)（按 ID 倒序）

---

### 用户管理

#### GET /api/admin/users

列出所有用户。

**响应** `200` — 数组，参见 [UserRead](#userread)（按创建时间倒序）

---

#### GET /api/admin/users/{user_id}

获取单个用户详情。

**响应** `200` — 参见 [UserRead](#userread)

---

#### POST /api/admin/users

创建用户。

**请求体**
```json
{
  "email": "user@example.com",
  "display_name": "张三",
  "password": "secure-password",
  "role": "member"
}
```
| 字段 | 约束 |
| --- | --- |
| `email` | 必填 |
| `display_name` | 必填，1-120 字符 |
| `password` | 必填，最少 8 字符 |
| `role` | 可选，`admin` 或 `member`，默认 `member` |

**响应** `200` — 参见 [UserRead](#userread)

**错误**
| 状态码 | 说明 |
| --- | --- |
| 409 | 用户邮箱已存在 |

---

#### PATCH /api/admin/users/{user_id}

更新用户信息。

**请求体**
```json
{
  "email": "new@example.com",
  "display_name": "新名字",
  "role": "admin"
}
```
所有字段均为可选。

**错误**
| 状态码 | 说明 |
| --- | --- |
| 404 | 用户不存在 |
| 409 | 新邮箱已被其他用户使用 |

---

#### POST /api/admin/users/{user_id}/password

重置用户密码。

**请求体**
```json
{ "password": "new-secure-password" }
```
| 字段 | 约束 |
| --- | --- |
| `password` | 必填，最少 8 字符 |

**响应** `200`
```json
{ "ok": true }
```

---

#### POST /api/admin/users/{user_id}/disable

禁用用户。

**响应** `200` — 参见 [UserRead](#userread)

**错误**
| 状态码 | 说明 |
| --- | --- |
| 400 | 不能禁用自己的账号 |

---

#### POST /api/admin/users/{user_id}/enable

启用用户。

**响应** `200` — 参见 [UserRead](#userread)

---

#### GET /api/admin/users/{user_id}/permissions

查看用户的图库权限。

**响应** `200` — 数组
```json
[
  {
    "user_id": 2,
    "library_id": 1,
    "can_view": true,
    "can_share": true
  }
]
```

---

#### PUT /api/admin/users/{user_id}/permissions

更新用户的图库权限（覆盖模式）。

**请求体** — 数组
```json
[
  {
    "library_id": 1,
    "can_view": true,
    "can_share": true
  },
  {
    "library_id": 2,
    "can_view": true,
    "can_share": false
  }
]
```

> 说明：提交的列表会完全覆盖该用户的权限。如果某个图库不在请求列表中，且之前有权限，则会被删除。如果 `can_view` 为 false，则会删除该图库的权限记录。

**响应** `200` — 更新后的权限数组

---

### 分享管理

#### GET /api/admin/shares

列出所有分享链接（包括已撤销的）。需要管理员角色。

**响应** `200` — 数组，参见 [ShareRead](#shareread)（按创建时间倒序）

#### PATCH /api/admin/shares/{share_id}

更新任意分享链接的标题、过期时间或密码。需要管理员角色。

**请求体** — 参见 `PATCH /api/shares/{share_id}`。

**响应** `200` — 参见 [ShareRead](#shareread)

#### DELETE /api/admin/shares/{share_id}

撤销任意分享链接。需要管理员角色。

**响应** `200`
```json
{ "ok": true }
```

---

### 文件系统浏览

#### GET /api/admin/filesystem/roots

列出文件系统根目录（推荐位置 + 系统盘符/挂载点）。

**响应** `200`
```json
{
  "platform": "Windows",
  "separator": "\\",
  "roots": [
    {
      "name": "Pictures",
      "path": "C:\\Users\\...\\Pictures",
      "is_root": false,
      "is_accessible": true,
      "kind": "folder",
      "group": "recommended",
      "child_folder_count": 5,
      "image_count": 120,
      "media_count": 0
    },
    {
      "name": "C:\\",
      "path": "C:\\",
      "is_root": true,
      "is_accessible": true,
      "kind": "drive",
      "group": "advanced"
    }
  ]
}
```

---

#### GET /api/admin/filesystem/children

浏览指定目录的子目录。

**查询参数**
| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `path` | string | 是 | 目标目录的绝对路径 |

**响应** `200`
```json
{
  "platform": "Windows",
  "separator": "\\",
  "path": "C:\\Users",
  "parent_path": "C:\\",
  "entries": [
    {
      "name": "Photos",
      "path": "C:\\Users\\Photos",
      "is_accessible": true,
      "kind": "folder",
      "child_folder_count": 3,
      "image_count": 50,
      "media_count": 2
    }
  ],
  "child_folder_count": 5,
  "image_count": 200,
  "media_count": 10
}
```

---

## 7. 健康检查

### GET /api/health

**响应** `200`
```json
{ "status": "ok" }
```

---

## 附录 A：数据模型参考

### UserRead
```json
{
  "id": 1,
  "email": "user@example.com",
  "display_name": "张三",
  "role": "admin",
  "is_active": true
}
```

### FolderRead
```json
{
  "id": 1,
  "library_id": 1,
  "parent_id": null,
  "path": "/photos",
  "name": "Family Photos",
  "photo_count": 42,
  "folder_count": 3,
  "cover_asset_id": 100,
  "updated_at": "2025-01-15T12:00:00"
}
```

### AssetRead
```json
{
  "id": 100,
  "library_id": 1,
  "folder_id": 5,
  "filename": "DSC_0001.JPG",
  "path": "2024/DSC_0001.JPG",
  "library_name": "Family Photos",
  "folder_name": "2024",
  "folder_path": "/photos/2024",
  "mime_type": "image/jpeg",
  "width": 6000,
  "height": 4000,
  "size": 8388608,
  "mtime": 1710000000.0,
  "captured_at": "2024-06-15T10:30:00",
  "camera_make": "Canon",
  "camera_model": "EOS R5",
  "lens_model": "EF24-70mm f/2.8L II USM",
  "iso": 100,
  "aperture": "f/2.8",
  "exposure_time": "1/250",
  "focal_length": "35mm",
  "latitude": 39.9042,
  "longitude": 116.4074,
  "tags": ["sunset", "beijing"],
  "description": "一张日落照片",
  "rating": 4,
  "updated_at": "2025-01-15T12:00:00",
  "is_favorite": true
}
```

### AlbumRead
```json
{
  "id": 1,
  "name": "我的相册",
  "description": "精选照片",
  "asset_count": 15,
  "cover_asset_id": 100,
  "created_at": "2025-01-10T08:00:00",
  "updated_at": "2025-01-15T12:00:00"
}
```

### ShareRead
```json
{
  "id": 1,
  "token": "aBcDeFgHiJkLmNoPqRsTuVwXyZ",
  "title": "分享标题",
  "asset_id": null,
  "folder_id": 5,
  "asset_ids": null,
  "asset_count": 20,
  "share_kind": "folder",
  "expires_at": "2025-02-15T12:00:00",
  "revoked_at": null,
  "created_at": "2025-01-15T12:00:00"
}
```
`share_kind` 取值：`asset`（单张）、`folder`（文件夹）、`assets`（多张）。

### LibraryRead
```json
{
  "id": 1,
  "name": "Family Photos",
  "path": "/photos",
  "is_enabled": true,
  "created_at": "2025-01-01T00:00:00",
  "last_scan_at": "2025-01-15T12:00:00"
}
```

### ScanJobRead
```json
{
  "id": 1,
  "library_id": 1,
  "status": "completed",
  "message": "Scan completed",
  "total_assets": 500,
  "started_at": "2025-01-15T12:00:00",
  "finished_at": "2025-01-15T12:05:00"
}
```
`status` 取值：`queued` → `running` → `completed` / `failed`。

---

## 附录 B：认证机制

### 登录流程
1. `POST /api/auth/login` 验证邮箱密码
2. 成功后生成 JWT Token，payload 包含 `sub`（用户 ID 字符串）和 `role`
3. Token 通过 HTTP-only Cookie `dk_photo_token` 发送，有效期 7 天
4. 后续请求自动携带 Cookie

### 权限层级
| 角色 | 说明 |
| --- | --- |
| `admin` | 可访问所有图库和所有管理功能 |
| `member` | 只能访问被授权（LibraryPermission）的图库；个人收藏、标签、评分、相册相互隔离 |

### 分享权限控制
- 成员需要 `can_share: true` 的 LibraryPermission 才能创建该图库的分享链接
- 管理员可创建任何图库的分享链接

---

## 附录 C：搜索功能

搜索原理（`/api/assets?search=关键词`）：

搜索会匹配以下字段：
- 文件名 (`filename`)
- 文件路径 (`path`)
- MIME 类型 (`mime_type`)
- 相机品牌 (`camera_make`)
- 相机型号 (`camera_model`)
- 镜头型号 (`lens_model`)
- 光圈 (`aperture`)
- 快门速度 (`exposure_time`)
- 焦距 (`focal_length`)
- ISO 值
- 拍摄时间
- 所在文件夹名称/路径
- 所在图库名称
- 用户标签
- 用户描述

使用 SQL `LIKE` 模式匹配（`contains`），所有条件用 `OR` 组合。
