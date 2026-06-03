# DK Photo

DK Photo 是一个自托管的私有家庭相册中心，基于 Vue 3 和 FastAPI 构建。它以只读方式索引配置的照片文件夹，将元数据和缩略图保存在应用数据目录中，并以文件夹视图为核心呈现照片库，操作体验类似群晖 Synology Photos。

## 功能特性

- **文件夹优先浏览**：支持多级嵌套文件夹，响应式照片网格布局。
- **只读索引**：支持 JPEG、PNG、WebP、GIF 格式，不修改原始文件。
- **SQLite 元数据库**：使用 SQLModel ORM 管理索引数据，Pillow 生成 WebP 缩略图。
- **实时文件监控**：基于 watchdog 监测文件系统变化，同时支持手动触发扫描。
- **内建用户系统**：管理员/成员两种角色，支持多用户。
- **完整用户管理**：创建/启用/禁用用户、重置密码、分配图库查看和分享权限。
- **文件系统浏览**：管理员可在页面上浏览服务器目录，选择新增图库路径。
- **私密分享链接**：支持分享单张照片、整个文件夹或多选照片，可设置过期时间（最长 365 天）。
- **右键快捷操作**：在图库文件夹上右键可**更改封面**或**重命名文件夹**。
- **多选与批量分享**：进入选择模式后可勾选多张照片，一键生成批量分享链接。
- **照片查看器**：全屏灯箱，支持键盘前后翻页、缩放及查看原图。
- **暗色/亮色主题**：支持一键切换，自动跟随系统偏好。
- **中英文双语界面**：支持中文和英文切换。
- **Docker Compose 部署**：前端 Nginx 静态托管 + 后端 Uvicorn，开箱即用。

## 快速开始

1. 复制 `.env.example` 为 `.env`。
2. 在 `.env` 中设置 `PHOTOS_PATH` 为你存放照片的主机目录路径。
3. 修改 `DK_PHOTO_ADMIN_EMAIL`、`DK_PHOTO_ADMIN_PASSWORD` 和 `DK_PHOTO_SECRET_KEY`。
4. 启动服务：

```powershell
docker compose up --build
```

打开 `http://localhost:8080`，使用管理员账号登录。登录后进入管理页面对默认图库进行扫描，或添加其他挂载的文件夹。

> 文件夹选择器显示的是后端进程可见的目录。在 Docker 环境中，这些是容器内路径（如 `/photos`）；请先在 `docker-compose.yml` 中挂载宿主机目录，再在管理页选择。添加图库时设置的名称会作为此图库**根文件夹的名称**。

## 本地开发

后端启动：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

前端启动：

```powershell
cd frontend
pnpm install
pnpm run dev
```

Vite 开发服务器会将 `/api` 请求代理到 `http://localhost:8000`。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DK_PHOTO_ADMIN_EMAIL` | `admin@example.com` | 初始管理员邮箱。 |
| `DK_PHOTO_ADMIN_PASSWORD` | `change-me-now` | 初始管理员密码，请务必修改。 |
| `DK_PHOTO_SECRET_KEY` | 开发默认值 | JWT 签名密钥，正式使用前务必修改。 |
| `DK_PHOTO_DATA_DIR` | `./data` | SQLite 数据库、缩略图及日志的存储目录。 |
| `DK_PHOTO_DEFAULT_LIBRARY_PATH` | 空 | 启动时若此路径存在则自动创建为默认图库。 |
| `DK_PHOTO_DEFAULT_LIBRARY_NAME` | `Family Photos` | 自动创建图库时的名称。 |
| `DK_PHOTO_CORS_ORIGINS` | 本地开发地址 | 允许的浏览器来源域名，逗号分隔。 |
| `DK_PHOTO_WATCH_ENABLED` | `true` | 是否启用 watchdog 文件监控自动扫描。 |

## API 概览

| 分组 | 接口 | 说明 |
| --- | --- | --- |
| 认证 | `POST /api/auth/login` | 登录 |
| | `GET /api/auth/me` | 获取当前用户信息 |
| | `POST /api/auth/logout` | 退出登录 |
| 文件夹 | `GET /api/folders` | 列出文件夹（按 parent_id / library_id 筛选） |
| | `GET /api/folders/{id}` | 获取文件夹详情（含祖先链） |
| | `PATCH /api/folders/{id}/cover` | 更改文件夹封面 |
| | `PATCH /api/folders/{id}/rename` | 重命名文件夹 |
| 文件资源 | `GET /api/assets` | 列出文件（按 folder_id / 搜索 / 递归） |
| | `GET /api/assets/{id}` | 获取文件元数据 |
| | `GET /api/assets/{id}/original` | 下载原始文件 |
| | `GET /api/assets/{id}/thumbnail` | 获取缩略图（小/中/大） |
| 分享 | `POST /api/shares` | 创建分享链接 |
| | `GET /api/public/shares/{token}` | 公开访问分享元数据 |
| | `GET /api/public/shares/{token}/assets` | 列出分享的文件 |
| | `GET /api/public/shares/{token}/assets/{id}/original` | 从分享下载原图 |
| | `GET /api/public/shares/{token}/assets/{id}/thumbnail` | 从分享获取缩略图 |
| 管理 | `GET/POST /api/admin/libraries` | 列出/创建图库 |
| | `PATCH /api/admin/libraries/{id}` | 更新图库名称 |
| | `DELETE /api/admin/libraries/{id}` | 删除图库及索引数据 |
| | `POST /api/admin/libraries/{id}/scan` | 触发扫描 |
| | `GET /api/admin/jobs` | 查看扫描任务 |
| | `GET/POST/PATCH /api/admin/users` | 用户管理 |
| | `POST /api/admin/users/{id}/password` | 重置密码 |
| | `POST /api/admin/users/{id}/enable` | 启用用户 |
| | `POST /api/admin/users/{id}/disable` | 禁用用户 |
| | `GET/PUT /api/admin/users/{id}/permissions` | 管理用户图库权限 |
| | `GET /api/admin/shares` | 列出所有分享 |
| | `GET /api/admin/filesystem/roots` | 列出文件系统根目录 |
| | `GET /api/admin/filesystem/children` | 浏览文件系统子目录 |

## 测试

后端测试：

```powershell
cd backend
pytest
```

前端检查：

```powershell
cd frontend
pnpm type-check
pnpm test:unit
```
